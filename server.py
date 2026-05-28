"""
AI Judge 预测池 Web 服务
部署到服务器后，用户访问网址即可看到实时预测池。

技术栈：
- FastAPI（轻量高性能）
- SQLite（本地数据库）
- APScheduler（定时任务：拉取赔率、结算比赛、生成报告）
- 静态 HTML（前端页面）
"""

import json
import sqlite3
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import contextmanager

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
        """)
        conn.commit()

# === 初始化席位 ===
SEATS = [
    {"id": "gemini",   "name": "Gemini",    "color": "#4285F4", "letter": "G"},
    {"id": "chatgpt",  "name": "ChatGPT",   "color": "#10A37F", "letter": "C"},
    {"id": "claude",   "name": "Claude",     "color": "#1E40AF", "letter": "Cl"},
    {"id": "yuanbao",  "name": "元宝",       "color": "#F59E0B", "letter": "Y"},
    {"id": "wenxin",   "name": "文心",       "color": "#3B82F6", "letter": "W"},
    {"id": "deepseek", "name": "DeepSeek",   "color": "#2563EB", "letter": "D"},
    {"id": "mimo",     "name": "MiMo",       "color": "#059669", "letter": "M"},
    {"id": "kimi",     "name": "Kimi",       "color": "#6366F1", "letter": "K"},
    {"id": "qwen",     "name": "通义",       "color": "#D97706", "letter": "Q"},
    {"id": "xai",      "name": "xAI",        "color": "#7C3AED", "letter": "X"},
    {"id": "zhipu",    "name": "智谱",       "color": "#0EA5E9", "letter": "Z"},
    {"id": "minimax",  "name": "MiniMax",    "color": "#EC4899", "letter": "MM"},
    {"id": "doubao",   "name": "豆包",       "color": "#EF4444", "letter": "豆"},
    {"id": "meta",     "name": "Meta AI",    "color": "#0668E1", "letter": "M"},
]

def seed_seats():
    with get_db() as conn:
        for seat in SEATS:
            conn.execute("""
                INSERT OR IGNORE INTO seats (seat_id, display_name, icon_color, icon_letter, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (seat["id"], seat["name"], seat["color"], seat["letter"],
                  datetime.now(timezone.utc).isoformat()))
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
        conn.commit()

# === API 查询函数 ===
def get_leaderboard():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT seat_id, display_name, icon_color, icon_letter,
                   balance, total_staked, total_won, total_lost,
                   forecasts, correct, loan_count, loan_total, strategy_tag
            FROM seats ORDER BY balance DESC
        """).fetchall()
        return [dict(r) for r in rows]

def get_matches(date=None):
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

def get_match_dates():
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT date, COUNT(*) as count FROM matches GROUP BY date ORDER BY date").fetchall()
        return [dict(r) for r in rows]

def get_stats():
    with get_db() as conn:
        seats = conn.execute("SELECT COUNT(*) as c FROM seats").fetchone()["c"]
        matches = conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()["c"]
        predictions = conn.execute("SELECT COUNT(*) as c FROM predictions").fetchone()["c"]
        settled = conn.execute("SELECT COUNT(*) as c FROM predictions WHERE result IS NOT NULL").fetchone()["c"]
        total_gp = conn.execute("SELECT SUM(balance) as s FROM seats").fetchone()["s"] or 0
        loans = conn.execute("SELECT COUNT(*) as c FROM loans WHERE status = 'active'").fetchone()["c"]
        return {
            "seats": seats,
            "matches": matches,
            "predictions": predictions,
            "settled": settled,
            "total_gp": round(total_gp),
            "active_loans": loans,
        }

# === 初始化 ===
def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    seed_seats()
    seed_matches()
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
