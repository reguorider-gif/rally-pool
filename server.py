"""
AI Judge 预测池 Web 服务
部署到服务器后，用户访问网址即可看到实时预测池。

技术栈：
- FastAPI（轻量高性能）
- SQLite（本地数据库）
- APScheduler（定时任务：拉取赔率、结算比赛、生成报告）
- 静态 HTML（前端页面）

P9.2 新增：支持从 data/pool/ 读取 JSON 数据（pool_data.py）。
"""

import json
import sqlite3
import hashlib
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import contextmanager

# === P9.2 新增：尝试导入 pool_data 数据加载层 ===
try:
    from pool_data import (
        get_model_accounts, get_archives_index, get_archive,
        get_matches as pd_get_matches, get_frontend_archives
    )
    _HAS_POOL_DATA = True
except Exception as _e:
    print(f"[server.py] WARNING: pool_data not available: {_e}")
    _HAS_POOL_DATA = False

# === 数据库 ===
DB_PATH = Path("/tmp") / "ai-judge-pool.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS seats (
            seat_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            icon_color TEXT NOT NULL,
            icon_letter TEXT NOT NULL,
            balance REAL DEFAULT 1000,
            total_staked REAL DEFAULT 0,
            total_won REAL DEFAULT 0,
            total_lost REAL DEFAULT 0,
            forecasts INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0,
            brier_scores TEXT DEFAULT '[]',
            loan_count INTEGER DEFAULT 0,
            loan_total REAL DEFAULT 0,
            strategy_tag TEXT DEFAULT 'unknown',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            home_team TEXT NOT NULL,
            home_flag TEXT,
            away_team TEXT NOT NULL,
            away_flag TEXT,
            match_type TEXT DEFAULT 'friendly',
            status TEXT DEFAULT 'scheduled',
            home_score INTEGER,
            away_score INTEGER,
            odds_home REAL,
            odds_draw REAL,
            odds_away REAL,
            prob_home REAL,
            prob_draw REAL,
            prob_away REAL,
            pool_total REAL DEFAULT 0,
            settled_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS predictions (
            pred_id TEXT PRIMARY KEY,
            match_id TEXT NOT NULL,
            seat_id TEXT NOT NULL,
            market TEXT NOT NULL,
            prediction TEXT NOT NULL,
            confidence REAL NOT NULL,
            stake REAL NOT NULL,
            odds REAL,
            ev REAL,
            result TEXT,
            payout REAL,
            profit REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (match_id) REFERENCES matches(match_id),
            FOREIGN KEY (seat_id) REFERENCES seats(seat_id)
        );

        CREATE TABLE IF NOT EXISTS loans (
            loan_id TEXT PRIMARY KEY,
            seat_id TEXT NOT NULL,
            amount REAL NOT NULL,
            interest_rate REAL DEFAULT 0.5,
            total_due REAL NOT NULL,
            repaid REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY (seat_id) REFERENCES seats(seat_id)
        );

        CREATE TABLE IF NOT EXISTS daily_logs (
            log_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            matches_played INTEGER DEFAULT 0,
            matches_settled INTEGER DEFAULT 0,
            gp_redistributed REAL DEFAULT 0,
            leaderboard_json TEXT,
            highlights TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS round_archives (
            archive_id TEXT PRIMARY KEY,
            round_id TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS model_packets (
            packet_id TEXT PRIMARY KEY,
            round_id TEXT NOT NULL,
            seat_id TEXT NOT NULL,
            prompt_context_json TEXT NOT NULL,
            response_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending_model_run',
            created_at TEXT NOT NULL,
            FOREIGN KEY (seat_id) REFERENCES seats(seat_id)
        );

        CREATE TABLE IF NOT EXISTS source_cards (
            source_id TEXT PRIMARY KEY,
            round_id TEXT NOT NULL,
            match_id TEXT,
            seat_id TEXT,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            confidence TEXT DEFAULT 'needs_review',
            needs_human_review INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """)
        conn.commit()

# === 初始化席位 ===
EXCLUDED_SEAT_IDS = {"claude", "zhipu"}
SEATS = [
    {"id": "gemini",   "name": "Gemini",    "color": "#4285F4", "letter": "G"},
    {"id": "chatgpt",  "name": "ChatGPT",   "color": "#10A37F", "letter": "C"},
    {"id": "yuanbao",  "name": "元宝",       "color": "#F59E0B", "letter": "Y"},
    {"id": "wenxin",   "name": "文心",       "color": "#3B82F6", "letter": "W"},
    {"id": "deepseek", "name": "DeepSeek",   "color": "#2563EB", "letter": "D"},
    {"id": "mimo",     "name": "MiMo",       "color": "#059669", "letter": "M"},
    {"id": "kimi",     "name": "Kimi",       "color": "#6366F1", "letter": "K"},
    {"id": "qwen",     "name": "通义",       "color": "#D97706", "letter": "Q"},
    {"id": "xai",      "name": "xAI",        "color": "#7C3AED", "letter": "X"},
    {"id": "minimax",  "name": "MiniMax",    "color": "#EC4899", "letter": "MM"},
    {"id": "doubao",   "name": "豆包",       "color": "#EF4444", "letter": "豆"},
    {"id": "meta",     "name": "Meta AI",    "color": "#0668E1", "letter": "M"},
]

RUN4_MODEL_ARCHIVE = {
    "deepseek": {"status": "recovered", "loan": "declined", "bets": "Finland +2.5 heavy; USA vs Senegal Under 2.5; Brazil -1.5 light", "risk": "Stop at -350GP; void Finland +2.5 if Germany starts full strength.", "source": "travel fatigue, Germany rotation, odds API, lineup confirmation"},
    "gemini": {"status": "recovered", "loan": "300GP development loan", "bets": "Norway win 300; Belgium-Croatia draw 400; France-CIV Under 2.5 500; Spain -1.5 300", "risk": "Stop after -600GP day; cancel if lineup overlap below 70%.", "source": "friendly starter minutes, Sweden rebuild, France hidden-strength pattern"},
    "chatgpt": {"status": "recovered", "loan": "declined", "bets": "Brazil -1.5 50; Senegal +0.5 35; Germany -1.5 55; Norway DNB 40; Belgium-Croatia Under 3 35; France -1 45; Spain -2 45; Spain futures 30", "risk": "Single-match cap 55GP; cancel below odds threshold or on heavy rotation.", "source": "FIFA/Reuters/NBC, injuries, odds thresholds"},
    "claude": {"status": "recovered", "loan": "300GP development loan", "bets": "Germany win + Over 2.5 200; Norway-Sweden draw 150; France win + Over 1.5 200; Spain -1.5 80; Belgium win 100", "risk": "Freeze at -350GP; cancel France if Mbappe absent; add Belgium if Modric absent.", "source": "injury board, Germany test XI, Spain rotation, travel fatigue"},
    "yuanbao": {"status": "recovered", "loan": "declined", "bets": "Brazil -2.5 150; USA-Senegal Under 2.5 120; Norway-Sweden draw 100; Belgium -0.5 130; France -1.5 140; Spain -2.5 160", "risk": "Cancel if lineup differs by 2+ starters; add 20% on favorable odds move >=0.2.", "source": "injury reports, odds movement, travel, locker room"},
    "wenxin": {"status": "recovered", "loan": "800GP high-risk expansion loan", "bets": "Norway-Sweden draw 200; Belgium-Croatia Under 2.25 300; France -1.5 600; Spain -2.5 820", "risk": "Main risk is favorite friendly under-effort; cancel Spain handicap without core midfield.", "source": "Belgium/Croatia fatigue, favorite rotation, Spain injuries"},
    "qwen": {"status": "recovered", "loan": "300GP development loan", "bets": "USA-Senegal BTTS & Under 2.5 150; Sweden DNB 200; Croatia +0.5 & Over 2.5 180; France -0.5 & Over 2.5 250; Spain -1 170", "risk": "Stop-loss 300GP; cancel if >3 key starters rested.", "source": "injuries, market consensus, pressing data, travel/timezone"},
    "kimi": {"status": "recovered", "loan": "declined", "bets": "Brazil -2.5 150; Over 3.5 100; Senegal X2 120; USA-Senegal Under 2.5 80; Germany -1.5 100; Norway win 100; group-stage preview 150", "risk": "Stop at 80% single-match loss; halve Brazil stake on rotation.", "source": "Yahoo Sports, RotoWire, 1xBet, Group I tactical notes"},
    "mimo": {"status": "recovered", "loan": "declined", "bets": "USA win 100 conditional; Norway win 150 conditional; Croatia DNB/+0.5 150; Belgium-Croatia draw 50; France-CIV Over 2.5 100", "risk": "Total stop 500GP; cancel on core absence; add if odds rise >10%.", "source": "FIFA ranking, tournament history, live odds, starters/injuries"},
    "minimax": {"status": "recovered", "loan": "declined", "bets": "Brazil -2.5/O2.5 120; USA-Senegal draw/U2.5 80; Germany -1.5/O2.5 100; Sweden DNB/draw 100; Belgium +0.25/O2.5 150; France -1.5/O2.5 200", "risk": "Max loss 750GP; avoid one-team ML below 1.5.", "source": "injury reports, training observations, odds movement, weather, travel fatigue"},
    "doubao": {"status": "recovered", "loan": "declined; if bottom 3 then 800GP high-risk loan", "bets": "Brazil -1.5 1200; France-CIV Over 2.5 1500; group-stage Spain win 1000", "risk": "Downgrade if human-supplied injury/window definitions are missing.", "source": "official pressers, FIFA/team social, Bet365, weather, tactical pressers"},
    "meta": {"status": "recovered", "loan": "not specified; rule-lock first", "bets": "No bet table; recommends locking 13-seat account snapshot and pending-settlement flags first.", "risk": "Loan seats must target 2.5x principal+interest; no-source heavy bet -100GP.", "source": "exclusive-source share, starters, weather, travel, locker-room credibility"},
    "xai": {"status": "missing_limit", "loan": "not submitted", "bets": "not submitted", "risk": "Grok returned free limit reached; not counted in consensus.", "source": "none"},
}

RUN4_SETTLEMENT_SIGNALS = {
    "deepseek": "Brazil -1.5 hit; Finland +2.5 and USA-Senegal Under 2.5 missed. Lower small-ball weight for Run #5.",
    "chatgpt": "Brazil -1.5 and Germany -1.5 hit; Senegal +0.5 missed. Small-stake discipline held.",
    "claude": "Germany win + Over 2.5 hit. Development-loan strategy remains eligible for another run.",
    "yuanbao": "Brazil -2.5 hit; USA-Senegal Under 2.5 missed. Add high-scoring friendly correction.",
    "kimi": "Brazil -2.5, Brazil Over 3.5 and Germany -1.5 hit; Senegal X2 and USA Under missed.",
    "minimax": "Brazil -2.5/O2.5 and Germany -1.5/O2.5 hit; USA draw/Under missed.",
    "doubao": "Brazil -1.5 heavy direction hit; require odds, repayment path and stop-loss before exact GP settlement.",
    "meta": "No bet table; its warning against premature ROI settlement was correct.",
    "xai": "No settlement because Grok did not submit a usable answer.",
}

RUN5_MODEL_ARCHIVE = {
    "deepseek": {
        "status": "valid_recovered",
        "loan": "1000GP development loan at 10%",
        "stake": "about 2810GP usable pool",
        "bets": "Shift to favorites/overs: Norway-Sweden over, France/Spain/Brazil/Germany handicap and over combinations.",
        "thought": "Run #4 punished Finland +2.5 and USA-Senegal under; lower warm-up small-ball weight while using the lead to borrow for information-backed upside.",
        "source": "Run #4 verified scores, FIFA schedule, starters/injuries pending, odds pending human confirmation",
        "risk": "No exact GP settlement without odds and handicap rules; reduce stake on rotation or line drop.",
    },
    "gemini": {
        "status": "valid_recovered",
        "loan": "1000GP investment loan; total pool 1850GP",
        "stake": "1850GP",
        "bets": "Norway-Sweden over 2.5 300; Spain -2.5 400; Brazil -1.5 400; Germany -1.0 350; France -2.0 400.",
        "thought": "Admits the small-ball/net-goal-decay model failed and raises warm-up xG baseline from 2.2 to 2.8.",
        "source": "FIFA schedule, Run #4 verified scores, favorites' lineup and press conference checks",
        "risk": "Cancel or reduce if Germany rotates, over line reaches 3.0, or Spain uses a full reserve XI.",
    },
    "qwen": {
        "status": "valid_recovered",
        "loan": "400GP development loan",
        "stake": "1500GP",
        "bets": "Norway-Sweden over 2.5 + Sweden -0.25 250; Belgium win + over 2.5 300; France -1.5 + over 2.5 300; Spain -2.5 + over 3.5 250; Brazil -1.5 + over 2.5 250; Germany win + over 2.5 150.",
        "thought": "Uses leverage to chase from mid-table, aligned with the verified favorite-handicap and over trend.",
        "source": "Run #4 post-match sample, schedule, starters/injuries/odds pending",
        "risk": "Combo markets add variance; reduce if odds fall below target or core players rest.",
    },
    "doubao": {
        "status": "valid_recovered",
        "loan": "300GP development loan; total pool 1400GP",
        "stake": "1400GP",
        "bets": "Norway-Sweden over 2.5 200; Belgium -0.5 + over 2.5 250; France -1.5 + over 2.5 300; Spain -2.5 + over 2.5 250; USA-Germany over 3.0 200; Brazil -1.5 + over 2.5 200.",
        "thought": "Brazil -1.5 heavy direction hit in Run #4, but bet count was too low; borrows to broaden coverage while keeping the warm-up over thesis.",
        "source": "Self-reported PP Sports, Weibo, 7M, Goal, Hupu, FotMob, Sohu; requires human reliability review",
        "risk": "Sources have mixed reliability; exact GP settlement waits for odds and source review.",
    },
    "chatgpt": {
        "status": "needs_rerun_context_polluted",
        "loan": "not recovered",
        "stake": "0",
        "bets": "Recovered text was old werewolf context: '我竞选警长'.",
        "thought": "Do not count in betting consensus; retain as contamination evidence.",
        "source": "CDP page text",
        "risk": "Rerun in a clean conversation.",
    },
    "claude": {
        "status": "audit_only_refusal",
        "loan": "declined betting loan",
        "stake": "0",
        "bets": "No position table or JSON betting receipt.",
        "thought": "Flags the virtual-GP loan/reward mechanic as a product risk because it may incentivize unsupported predictions.",
        "source": "model self-reported capability boundary and schedule-observation feedback",
        "risk": "Keep as risk/compliance audit, not betting consensus.",
    },
    "yuanbao": {
        "status": "valid_recovered",
        "loan": "500GP investment loan at 10%",
        "stake": "about 1500GP",
        "bets": "Brazil -1.5 300; Argentina first-half under 1.5 200; France ML 250; Netherlands -1 150; Türkiye ML 100.",
        "thought": "Follows favorites where evidence is dense, but looks for half-time under or contrarian angles where opponents crowd the same match.",
        "source": "FIFA friendly schedule, European sports media, odds/injuries pending review",
        "risk": "Pause new positions after two matches below ROI 1.3 and prioritize loan repayment.",
    },
    "kimi": {"status": "needs_rerun_placeholder", "loan": "not recovered", "stake": "0", "bets": "placeholder only", "thought": "Low-GP comeback seat still needs loan/high-odds plan.", "source": "CDP page text", "risk": "Force JSON receipt on rerun."},
    "wenxin": {"status": "needs_rerun_placeholder", "loan": "not recovered", "stake": "0", "bets": "placeholder only", "thought": "No valid bet table.", "source": "CDP page text", "risk": "Use shorter context on rerun."},
    "minimax": {"status": "needs_rerun_placeholder", "loan": "not recovered", "stake": "0", "bets": "placeholder only", "thought": "No valid bet table.", "source": "CDP page text", "risk": "Confirm Agent page is in chat state."},
    "mimo": {
        "status": "valid_recovered",
        "loan": "300GP investment loan at 10%",
        "stake": "1200GP planned bets / 700GP buffer",
        "bets": "Mexico ML 300 and four additional travel/rotation/home-field edge positions including USA-Germany.",
        "thought": "Uses travel fatigue, altitude home field, and rotation pressure to attack factors pure probability models may underprice.",
        "source": "FIFA schedule, home/travel distance, coach rotation signals, starters pending confirmation",
        "risk": "Three of five hits should cover 330GP principal+interest; reduce on heavy rotation.",
    },
    "meta": {
        "status": "valid_recovered",
        "loan": "800GP high-risk expansion credit at 30%",
        "stake": "1400PTS allocation / 500PTS buffer",
        "bets": "Canada -0.5; Norway-Sweden under 2.5; Côte d'Ivoire +1.5; plus five more small high-frequency positions.",
        "thought": "Leans into social-context and home/travel narratives to counter narrow data-model paths.",
        "source": "FIFA schedule, home narrative, travel fatigue, starters/venue pending confirmation",
        "risk": "Loan requires at least 1040PTS return; cancel on lineup or venue changes.",
    },
    "xai": {"status": "quota_blocked", "loan": "not recovered", "stake": "0", "bets": "Grok free limit reached.", "thought": "Cannot rerun until quota/login is restored.", "source": "Grok page notice", "risk": "Exclude from consensus until available."},
}

def seed_seats():
    with get_db() as conn:
        for seat in SEATS:
            conn.execute("""
                INSERT OR IGNORE INTO seats (seat_id, display_name, icon_color, icon_letter, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (seat["id"], seat["name"], seat["color"], seat["letter"],
                  datetime.now(timezone.utc).isoformat()))
        conn.commit()

def stable_id(*parts):
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

def decode_json(value, fallback=None):
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback

def seed_archives():
    now = datetime.now(timezone.utc).isoformat()
    round_payload = {
        "round_id": "run-4",
        "status": "settlement_review_ready_12_of_13",
        "run_id": "0580e924decf",
        "recovery": {"method": "chrome_cdp_page_text", "recovered": 12, "missing": ["xai"], "missing_reason": "Grok free limit reached"},
        "settled_results": [
            {"match_id": "UCL-001", "result": "PSG 1-1 Arsenal, PSG won on penalties", "status": "settled", "source": "UEFA post-match record"},
            {"match_id": "WARM-002", "result": "Brazil 6-2 Panama", "status": "verified_score_pending_odds", "source": "FIFA / CBF match report"},
            {"match_id": "WARM-003", "result": "USA 3-2 Senegal", "status": "verified_score_pending_odds", "source": "U.S. Soccer match report"},
            {"match_id": "WARM-004", "result": "Germany 4-0 Finland", "status": "verified_score_pending_odds", "source": "DFB match report"}
        ],
        "pending_results": [],
        "settlement_note": "Scores are verified; exact GP settlement still waits for odds, handicap, combo-bet and void/push rules.",
        "rules": {
            "development_loan": "300GP / 10%",
            "emergency_loan": "500GP / 20%",
            "high_risk_expansion_loan": "800GP / 30%",
            "top_rewards": {"rank_1": 300, "rank_2": 200, "rank_3": 100},
            "most_improved": 150,
            "best_source_contribution": 100,
            "comeback_bonus": 200,
        },
        "writeback_fields": [
            "model_account", "loan_decision", "bet_ledger", "betting_thought",
            "source_cards", "risk_rules", "opponent_context", "settlement_pending"
        ],
    }
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO round_archives
            (archive_id, round_id, title, status, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            stable_id("archive", "run-4"),
            "run-4",
            "Run #4 post-match archive and Run #5 opening packet",
            "settlement_review_ready_12_of_13",
            json.dumps(round_payload, ensure_ascii=False),
            now,
        ))
        for index, seat in enumerate(SEATS, start=1):
            context = {
                "rank": index,
                "current_balance_gp": 1000,
                "excluded_seats": sorted(EXCLUDED_SEAT_IDS),
                "opponent_context": "Models receive leaderboard, previous bet result, loan policy, and opponent results before betting.",
                "required_output": round_payload["writeback_fields"],
            }
            response = dict(RUN4_MODEL_ARCHIVE.get(seat["id"], {}))
            response["settlement_signal"] = RUN4_SETTLEMENT_SIGNALS.get(
                seat["id"],
                "No direct 5/31 settlement signal; carry Run #4 context into Run #5."
            )
            conn.execute("""
                INSERT OR REPLACE INTO model_packets
                (packet_id, round_id, seat_id, prompt_context_json, response_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                stable_id("packet", "run-4", seat["id"]),
                "run-4",
                seat["id"],
                json.dumps(context, ensure_ascii=False),
                json.dumps(response, ensure_ascii=False),
                response.get("status", "pending_model_run"),
                now,
            ))
        for match_id, title, source_type, summary, confidence, needs_review in [
            ("WARM-002", "Brazil vs Panama result and settlement board", "post_match", "Verified score: Brazil 6-2 Panama. Brazil handicap and over positions are directionally positive; exact GP waits for odds/line confirmation.", "verified_score", 1),
            ("WARM-003", "USA vs Senegal result and settlement board", "post_match", "Verified score: USA 3-2 Senegal. USA win positions are directionally positive; Senegal +0.5 and under positions missed.", "verified_score", 1),
            ("WARM-004", "Germany vs Finland result and settlement board", "post_match", "Verified score: Germany 4-0 Finland. Germany -1.5 / win+over positions hit; Finland +2.5 and low-score thesis missed.", "verified_score", 1),
            (None, "Loan and incentive policy", "rules", "Run #5 should use the 5/31 settlement signals, loan incentives, and source-quality requirements before new bets.", "needs_review", 1),
        ]:
            conn.execute("""
                INSERT OR REPLACE INTO source_cards
                (source_id, round_id, match_id, source_type, title, summary, confidence, needs_human_review, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stable_id("source", "run-4", match_id or title),
                "run-4",
                match_id,
                source_type,
                title,
                summary,
                confidence,
                needs_review,
                now,
            ))
        run5_payload = {
            "round_id": "run-5",
            "status": "recovered_7_of_13_plus_1_audit",
            "run_id": "84e6a904e064",
            "supplement_run_ids": ["25bc481758c8", "2261bf6ae0a2"],
            "valid_recovered": ["deepseek", "gemini", "qwen", "doubao", "yuanbao", "mimo", "meta"],
            "audit_only": ["claude"],
            "needs_rerun": ["chatgpt", "kimi", "wenxin", "minimax"],
            "quota_blocked": ["xai"],
            "bridge_blocker": {
                "kind": "werewolf",
                "run_id": "werewolf-f14863477d89 / werewolf-a5049ebc77dd",
                "reason": "First supplement was blocked by an active werewolf session; second supplement recovered Yuanbao, MiMo and Meta, then the bridge was taken by a new werewolf session before remaining reruns could continue.",
            },
            "input_results": round_payload["settled_results"],
            "rules": round_payload["rules"],
            "settlement_note": "Run #5 contains real recovered betting strategies for 7 seats plus Claude risk audit. The remaining seats require a clean rerun or quota recovery before consensus and settlement.",
            "writeback_fields": [
                "model_account", "loan_decision", "bet_ledger", "betting_thought",
                "source_cards", "risk_rules", "opponent_context", "rerun_status"
            ],
        }
        conn.execute("""
            INSERT OR REPLACE INTO round_archives
            (archive_id, round_id, title, status, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            stable_id("archive", "run-5"),
            "run-5",
            "Run #5 recovered model betting archive",
            "recovered_7_of_13_plus_1_audit",
            json.dumps(run5_payload, ensure_ascii=False),
            now,
        ))
        for index, seat in enumerate(SEATS, start=1):
            context = {
                "rank": index,
                "current_balance_gp": 1000,
                "run4_verified_results": round_payload["settled_results"],
                "loan_policy": round_payload["rules"],
                "opponent_context": "Run #5 prompt included current balance, leaderboard, Run #4 verified score signals, opponent results, loan incentives, and source collection requirements.",
                "required_output": run5_payload["writeback_fields"],
            }
            response = dict(RUN5_MODEL_ARCHIVE.get(seat["id"], {
                "status": "not_requested",
                "loan": "not recovered",
                "stake": "0",
                "bets": "not submitted",
                "thought": "Seat was not part of the recovered Run #5 archive.",
                "source": "none",
                "risk": "not counted",
            }))
            conn.execute("""
                INSERT OR REPLACE INTO model_packets
                (packet_id, round_id, seat_id, prompt_context_json, response_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                stable_id("packet", "run-5", seat["id"]),
                "run-5",
                seat["id"],
                json.dumps(context, ensure_ascii=False),
                json.dumps(response, ensure_ascii=False),
                response.get("status", "pending_rerun"),
                now,
            ))
        for match_id, title, source_type, summary, confidence, needs_review in [
            (None, "Run #5 valid recovered model answers", "model_archive", "Valid Run #5 strategies recovered for DeepSeek, Gemini, Qwen, Doubao, Yuanbao, MiMo and Meta. Claude is retained as risk audit only.", "verified_capture", 0),
            (None, "Run #5 rerun queue", "rerun_queue", "ChatGPT context pollution; Kimi/Wenxin/MiniMax placeholders; xAI quota block. These seats are not counted in consensus.", "needs_rerun", 1),
            (None, "Fixed bridge blocker", "execution_blocker", "Supplement run 25bc481758c8 was blocked by active werewolf-f14863477d89. Later supplement 2261bf6ae0a2 recovered three more seats but ended with API status stuck; cancelled after CDP capture.", "runtime_evidence", 1),
            (None, "Odds and lineup verification queue", "source_task", "Before settlement, collect actual pre-match odds, handicap lines, lineups, injuries, weather, and source reliability for each target match.", "needs_review", 1),
        ]:
            conn.execute("""
                INSERT OR REPLACE INTO source_cards
                (source_id, round_id, match_id, source_type, title, summary, confidence, needs_human_review, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stable_id("source", "run-5", match_id or title),
                "run-5",
                match_id,
                source_type,
                title,
                summary,
                confidence,
                needs_review,
                now,
            ))
        conn.commit()

# === 比赛数据 ===
MATCHES = [
    {"id": "WARM-001", "date": "2026-05-28", "home": "Egypt", "hf": "🇪🇬", "away": "Russia", "af": "🇷🇺", "type": "friendly", "oh": 2.10, "od": 3.20, "oa": 3.50, "ph": 0.48, "pd": 0.31, "pa": 0.21},
    {"id": "WARM-002", "date": "2026-05-31", "home": "Brazil", "hf": "🇧🇷", "away": "Panama", "af": "🇵🇦", "type": "friendly", "oh": 1.15, "od": 7.00, "oa": 15.00, "ph": 0.87, "pd": 0.09, "pa": 0.04},
    {"id": "WARM-003", "date": "2026-05-31", "home": "USA", "hf": "🇺🇸", "away": "Senegal", "af": "🇸🇳", "type": "friendly", "oh": 2.00, "od": 3.30, "oa": 3.80, "ph": 0.50, "pd": 0.30, "pa": 0.26},
    {"id": "WARM-004", "date": "2026-05-31", "home": "Germany", "hf": "🇩🇪", "away": "Finland", "af": "🇫🇮", "type": "friendly", "oh": 1.25, "od": 5.50, "oa": 12.00, "ph": 0.80, "pd": 0.14, "pa": 0.06},
    {"id": "WARM-005", "date": "2026-06-01", "home": "Norway", "hf": "🇳🇴", "away": "Sweden", "af": "🇸🇪", "type": "darkhorse", "oh": 2.30, "od": 3.20, "oa": 3.10, "ph": 0.43, "pd": 0.31, "pa": 0.32},
    {"id": "WARM-006", "date": "2026-06-02", "home": "Belgium", "hf": "🇧🇪", "away": "Croatia", "af": "🇭🇷", "type": "friendly", "oh": 2.20, "od": 3.30, "oa": 3.20, "ph": 0.45, "pd": 0.30, "pa": 0.31},
    {"id": "WARM-007", "date": "2026-06-04", "home": "France", "hf": "🇫🇷", "away": "Ivory Coast", "af": "🇨🇮", "type": "favorite", "oh": 1.30, "od": 5.00, "oa": 10.00, "ph": 0.77, "pd": 0.16, "pa": 0.07},
    {"id": "WARM-008", "date": "2026-06-04", "home": "Iraq", "hf": "🇮🇶", "away": "Spain", "af": "🇪🇸", "type": "friendly", "oh": 12.00, "od": 6.00, "oa": 1.20, "ph": 0.08, "pd": 0.12, "pa": 0.80},
    {"id": "WARM-009", "date": "2026-06-06", "home": "USA", "hf": "🇺🇸", "away": "Germany", "af": "🇩🇪", "type": "marquee", "oh": 2.80, "od": 3.20, "oa": 2.50, "ph": 0.36, "pd": 0.31, "pa": 0.40},
    {"id": "WARM-010", "date": "2026-06-06", "home": "England", "hf": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "away": "New Zealand", "af": "🇳🇿", "type": "friendly", "oh": 1.10, "od": 8.00, "oa": 20.00, "ph": 0.91, "pd": 0.07, "pa": 0.02},
    {"id": "WARM-011", "date": "2026-06-06", "home": "Brazil", "hf": "🇧🇷", "away": "Egypt", "af": "🇪🇬", "type": "friendly", "oh": 1.40, "od": 4.50, "oa": 7.50, "ph": 0.71, "pd": 0.18, "pa": 0.11},
    {"id": "WARM-012", "date": "2026-06-06", "home": "Morocco", "hf": "🇲🇦", "away": "Norway", "af": "🇳🇴", "type": "darkhorse", "oh": 2.20, "od": 3.20, "oa": 3.30, "ph": 0.45, "pd": 0.31, "pa": 0.30},
    {"id": "WARM-013", "date": "2026-06-09", "home": "Spain", "hf": "🇪🇸", "away": "Peru", "af": "🇵🇪", "type": "favorite", "oh": 1.15, "od": 7.00, "oa": 15.00, "ph": 0.87, "pd": 0.09, "pa": 0.04},
    # WC Group Stage (selected)
    {"id": "WC-A1", "date": "2026-06-11", "home": "Mexico", "hf": "🇲🇽", "away": "South Africa", "af": "🇿🇦", "type": "wc_group", "oh": 1.50, "od": 4.00, "oa": 6.50, "ph": 0.67, "pd": 0.25, "pa": 0.15},
    {"id": "WC-H1", "date": "2026-06-14", "home": "Spain", "hf": "🇪🇸", "away": "Cape Verde", "af": "🇨🇻", "type": "wc_group", "oh": 1.08, "od": 10.00, "oa": 29.00, "ph": 0.93, "pd": 0.05, "pa": 0.02},
    {"id": "WC-I1", "date": "2026-06-14", "home": "France", "hf": "🇫🇷", "away": "Senegal", "af": "🇸🇳", "type": "wc_group", "oh": 1.35, "od": 4.80, "oa": 8.50, "ph": 0.74, "pd": 0.21, "pa": 0.12},
    {"id": "WC-F1", "date": "2026-06-14", "home": "Netherlands", "hf": "🇳🇱", "away": "Japan", "af": "🇯🇵", "type": "wc_group", "oh": 1.80, "od": 3.50, "oa": 4.20, "ph": 0.56, "pd": 0.29, "pa": 0.24},
    {"id": "WC-H2", "date": "2026-06-19", "home": "Spain", "hf": "🇪🇸", "away": "Uruguay", "af": "🇺🇾", "type": "wc_group", "oh": 1.60, "od": 3.80, "oa": 5.50, "ph": 0.63, "pd": 0.26, "pa": 0.18},
    {"id": "WC-I2", "date": "2026-06-19", "home": "France", "hf": "🇫🇷", "away": "Norway", "af": "🇳🇴", "type": "wc_group", "oh": 1.45, "od": 4.20, "oa": 7.00, "ph": 0.69, "pd": 0.24, "pa": 0.14},
    {"id": "WC-F2", "date": "2026-06-19", "home": "Netherlands", "hf": "🇳🇱", "away": "Sweden", "af": "🇸🇪", "type": "wc_group", "oh": 1.90, "od": 3.40, "oa": 3.80, "ph": 0.53, "pd": 0.29, "pa": 0.26},
    {"id": "WC-K1", "date": "2026-06-15", "home": "Portugal", "hf": "🇵🇹", "away": "Colombia", "af": "🇨🇴", "type": "wc_group", "oh": 1.75, "od": 3.60, "oa": 4.80, "ph": 0.57, "pd": 0.28, "pa": 0.21},
]

def seed_matches():
    with get_db() as conn:
        for m in MATCHES:
            conn.execute("""
                INSERT OR IGNORE INTO matches
                (match_id, date, home_team, home_flag, away_team, away_flag, match_type,
                 odds_home, odds_draw, odds_away, prob_home, prob_draw, prob_away, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')
            """, (m["id"], m["date"], m["home"], m["hf"], m["away"], m["af"], m["type"],
                  m["oh"], m["od"], m["oa"], m["ph"], m["pd"], m["pa"]))
        for match_id, home_score, away_score in [
            ("WARM-002", 6, 2),
            ("WARM-003", 3, 2),
            ("WARM-004", 4, 0),
        ]:
            conn.execute("""
                UPDATE matches
                SET status = 'settled', home_score = ?, away_score = ?
                WHERE match_id = ?
            """, (home_score, away_score, match_id))
        conn.commit()

# === API 查询函数 ===
def get_leaderboard():
    """
    P9.2：优先从 pool_data 读取 model_accounts/current.json，
    失败再 fallback 到 SQLite。
    """
    if _HAS_POOL_DATA:
        try:
            data = get_model_accounts()
            if data and data.get("models"):
                seats = []
                for m in data["models"]:
                    seats.append({
                        "seat_id": m.get("model_account", ""),
                        "display_name": m.get("display_name", ""),
                        "icon_color": m.get("icon_color", ""),
                        "icon_letter": m.get("icon_letter", ""),
                        "balance": 1000,
                        "total_staked": 0,
                        "total_won": 0,
                        "total_lost": 0,
                        "forecasts": 0,
                        "correct": 0,
                        "loan_count": 0,
                        "loan_total": 0,
                        "strategy_tag": "unknown",
                    })
                # 按 balance 降序（当前都是 1000，稳定排序）
                seats.sort(key=lambda x: x["balance"], reverse=True)
                return seats
        except Exception as e:
            print(f"[get_leaderboard] pool_data failed, fallback to SQLite: {e}", file=sys.stderr)
    # fallback to SQLite
    with get_db() as conn:
        rows = conn.execute("""
            SELECT seat_id, display_name, icon_color, icon_letter,
                   balance, total_staked, total_won, total_lost,
                   forecasts, correct, loan_count, loan_total, strategy_tag
            FROM seats WHERE seat_id != 'zhipu' ORDER BY balance DESC
        """).fetchall()
        return [dict(r) for r in rows]

def get_matches(date=None):
    """
    P9.2：优先从 pool_data 读取 matches/current.json，
    失败再 fallback 到 SQLite。
    """
    if _HAS_POOL_DATA:
        try:
            data = pd_get_matches()
            if data and data.get("matches"):
                results = []
                for m in data["matches"]:
                    row = {
                        "match_id": m.get("match_id", ""),
                        "date": m.get("date", ""),
                        "home_team": m.get("home_team", ""),
                        "home_flag": m.get("home_flag", ""),
                        "away_team": m.get("away_team", ""),
                        "away_flag": m.get("away_flag", ""),
                        "match_type": m.get("competition", "friendly"),
                        "status": m.get("status", "scheduled"),
                        "home_score": m.get("home_score"),
                        "away_score": m.get("away_score"),
                        "odds_home": m.get("odds_home", 0),
                        "odds_draw": m.get("odds_draw", 0),
                        "odds_away": m.get("odds_away", 0),
                        "prob_home": m.get("prob_home", 0),
                        "prob_draw": m.get("prob_draw", 0),
                        "prob_away": m.get("prob_away", 0),
                    }
                    if date is None or row["date"] == date:
                        results.append(row)
                return results
        except Exception as e:
            print(f"[get_matches] pool_data failed, fallback to SQLite: {e}", file=sys.stderr)
    # fallback to SQLite
    with get_db() as conn:
        if date:
            rows = conn.execute("SELECT * FROM matches WHERE date = ? ORDER BY date", (date,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM matches ORDER BY date").fetchall()
        return [dict(r) for r in rows]

def get_match_predictions(match_id):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.*, s.display_name, s.icon_color, s.icon_letter
            FROM predictions p JOIN seats s ON p.seat_id = s.seat_id
            WHERE p.match_id = ? ORDER BY p.stake DESC
        """, (match_id,)).fetchall()
        return [dict(r) for r in rows]

def get_seat_predictions(seat_id):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.*, m.home_team, m.home_flag, m.away_team, m.away_flag, m.date
            FROM predictions p JOIN matches m ON p.match_id = m.match_id
            WHERE p.seat_id = ? ORDER BY m.date
        """, (seat_id,)).fetchall()
        return [dict(r) for r in rows]

def get_seat_loans(seat_id):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM loans WHERE seat_id = ? ORDER BY created_at", (seat_id,)).fetchall()
        return [dict(r) for r in rows]

def get_daily_logs():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM daily_logs ORDER BY date DESC LIMIT 14").fetchall()
        return [dict(r) for r in rows]

def get_round_archives():
    """
    P9.2：优先从 pool_data 读取 archives/index.json，
    失败再 fallback 到 SQLite。
    """
    if _HAS_POOL_DATA:
        try:
            index = get_archives_index()
            if index and index.get("rounds"):
                results = []
                for r in index.get("rounds", []):
                    round_id = r.get("round_id", "")
                    file_ref = r.get("file", "")
                    item = {
                        "archive_id": file_ref or round_id,
                        "round_id": round_id,
                        "title": r.get("title", ""),
                        "status": r.get("status", ""),
                        "payload_json": json.dumps(pd_get_archive(round_id) if pd_get_archive(round_id) else {}),
                        "created_at": r.get("updated_at", ""),
                    }
                    results.append(item)
                if results:
                    return results
        except Exception as e:
            print(f"[get_round_archives] pool_data failed, fallback to SQLite: {e}", file=sys.stderr)
    # fallback to SQLite
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM round_archives ORDER BY created_at DESC").fetchall()
        archives = []
        for row in rows:
            item = dict(row)
            item["payload"] = decode_json(item.pop("payload_json", None), {})
            archives.append(item)
        return archives

def get_round_archive(round_id):
    with get_db() as conn:
        archive = conn.execute("SELECT * FROM round_archives WHERE round_id = ?", (round_id,)).fetchone()
        packets = conn.execute("SELECT * FROM model_packets WHERE round_id = ? ORDER BY seat_id", (round_id,)).fetchall()
        sources = conn.execute("SELECT * FROM source_cards WHERE round_id = ? ORDER BY source_type, match_id", (round_id,)).fetchall()
        archive_item = dict(archive) if archive else None
        if archive_item:
            archive_item["payload"] = decode_json(archive_item.pop("payload_json", None), {})
        packet_items = []
        for row in packets:
            item = dict(row)
            item["prompt_context"] = decode_json(item.pop("prompt_context_json", None), {})
            item["response"] = decode_json(item.pop("response_json", None), {})
            packet_items.append(item)
        return {
            "archive": archive_item,
            "packets": packet_items,
            "sources": [dict(r) for r in sources],
        }

def get_match_dates():
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT date, COUNT(*) as count FROM matches GROUP BY date ORDER BY date").fetchall()
        return [dict(r) for r in rows]

def get_stats():
    """
    P9.2：优先从 pool_data 读取模型数/赛事数，
    失败再 fallback 到 SQLite。
    """
    result = {
        "seats": 13,
        "matches": 22,
        "predictions": 0,
        "settled": 0,
        "total_gp": 13000,
        "active_loans": 0,
    }
    if _HAS_POOL_DATA:
        try:
            models_data = get_model_accounts()
            if models_data and models_data.get("models"):
                result["seats"] = len([m for m in models_data["models"] if m.get("model_account") != "zhipu"])
            matches_data = pd_get_matches()
            if matches_data and matches_data.get("matches"):
                result["matches"] = len(matches_data["matches"])
        except Exception as e:
            print(f"[get_stats] pool_data failed, fallback to SQLite: {e}", file=sys.stderr)
    # fallback / supplement from SQLite
    try:
        with get_db() as conn:
            seats = conn.execute("SELECT COUNT(*) as c FROM seats WHERE seat_id != 'zhipu'").fetchone()["c"]
            matches = conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()["c"]
            predictions = conn.execute("SELECT COUNT(*) as c FROM predictions").fetchone()["c"]
            settled = conn.execute("SELECT COUNT(*) as c FROM predictions WHERE result IS NOT NULL").fetchone()["c"]
            total_gp = conn.execute("SELECT SUM(balance) as s FROM seats WHERE seat_id != 'zhipu'").fetchone()["s"] or 0
            loans = conn.execute("SELECT COUNT(*) as c FROM loans WHERE status = 'active'").fetchone()["c"]
            # 只在 SQLite 有数据时用它覆盖（pool_data 可能没有 counts）
            if seats:
                result["seats"] = seats
            if matches:
                result["matches"] = matches
            result["predictions"] = predictions
            result["settled"] = settled
            result["total_gp"] = round(total_gp)
            result["active_loans"] = loans
    except Exception as e:
        print(f"[get_stats] SQLite fallback failed: {e}", file=sys.stderr)
    return result

# === 初始化 ===
def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    seed_seats()
    seed_matches()
    seed_archives()
    print(f"Database initialized at {DB_PATH}")
    print(f"Seats: {len(SEATS)}")
    print(f"Matches: {len(MATCHES)}")

if __name__ == "__main__":
    init()
    print("\nStats:", get_stats())
    print("\nLeaderboard:")
    for seat in get_leaderboard():
        print(f"  {seat['icon_letter']} {seat['display_name']}: {seat['balance']} GP")
    print("\nMatch dates:")
    for d in get_match_dates():
        print(f"  {d['date']}: {d['count']} matches")
