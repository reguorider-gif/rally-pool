AI_JUDGE_RUN_MARKER:AI_JUDGE_RUN_MARKER:POOL_RUN-6_20260603

# AI Judge 赛事预测池独立模型席位

seat_id: qwen
model_account: qwen
display_name: 通义
round_id: run-6
date: 2026-06-03

【合规与实验边界】
这是虚拟 GP 预测研究，不涉及真钱下注，不构成现实博彩建议。
所有投注均为模拟，仅用于算法研究与模型评估。

## 当前任务
你是 AI Judge 赛事预测池中的一个独立模型席位。
你必须基于给定赛程、赛果状态、赔率快照、资金/风控约束，输出结构化 JSON 投注单。

## 强制防污染要求
- 不要回答旧任务。
- 不要回答狼人杀、警长投票、守卫、平民、预言家、Grand Judge 等无关任务。
- 不要输出你的最终答案。
- 不要输出 Markdown。
- 不要输出解释性自然语言。
- 不要输出 JSON 之外的任何内容。
- JSON 必须能被 json.loads 解析。

## 可用比赛摘要
{
  "matches_total": 21,
  "sample_matches": [
    {
      "match_id": "WARM-001",
      "date": "2026-05-28",
      "home_team": "Egypt",
      "home_flag": "🇪",
      "away_team": "Russia",
      "away_flag": "🇷",
      "competition": "friendly",
      "status": "scheduled",
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 2.1,
      "odds_draw": 3.2,
      "odds_away": 3.5,
      "prob_home": 0.48,
      "prob_draw": 0.31,
      "prob_away": 0.21,
      "kickoff_at": "2026-05-28T00:00:00Z"
    },
    {
      "match_id": "WARM-002",
      "date": "2026-05-31",
      "home_team": "Brazil",
      "home_flag": "🇧",
      "away_team": "Panama",
      "away_flag": "🇵",
      "competition": "friendly",
      "status": "settled",
      "home_score": 6,
      "away_score": 2,
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 1.15,
      "odds_draw": 7.0,
      "odds_away": 15.0,
      "prob_home": 0.87,
      "prob_draw": 0.09,
      "prob_away": 0.04,
      "kickoff_at": "2026-05-31T00:00:00Z"
    },
    {
      "match_id": "WARM-003",
      "date": "2026-05-31",
      "home_team": "USA",
      "home_flag": "🇺",
      "away_team": "Senegal",
      "away_flag": "🇸",
      "competition": "friendly",
      "status": "settled",
      "home_score": 3,
      "away_score": 2,
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 2.0,
      "odds_draw": 3.3,
      "odds_away": 3.8,
      "prob_home": 0.5,
      "prob_draw": 0.3,
      "prob_away": 0.26,
      "kickoff_at": "2026-05-31T00:00:00Z"
    },
    {
      "match_id": "WARM-004",
      "date": "2026-05-31",
      "home_team": "Germany",
      "home_flag": "🇩",
      "away_team": "Finland",
      "away_flag": "🇫",
      "competition": "friendly",
      "status": "settled",
      "home_score": 4,
      "away_score": 0,
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 1.25,
      "odds_draw": 5.5,
      "odds_away": 12.0,
      "prob_home": 0.8,
      "prob_draw": 0.14,
      "prob_away": 0.06,
      "kickoff_at": "2026-05-31T00:00:00Z"
    },
    {
      "match_id": "WARM-005",
      "date": "2026-06-01",
      "home_team": "Norway",
      "home_flag": "🇳",
      "away_team": "Sweden",
      "away_flag": "🇸",
      "competition": "darkhorse",
      "status": "scheduled",
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 2.3,
      "odds_draw": 3.2,
      "odds_away": 3.1,
      "prob_home": 0.43,
      "prob_draw": 0.31,
      "prob_away": 0.32,
      "kickoff_at": "2026-06-01T00:00:00Z"
    },
    {
      "match_id": "WARM-006",
      "date": "2026-06-02",
      "home_team": "Belgium",
      "home_flag": "🇧",
      "away_team": "Croatia",
      "away_flag": "🇭",
      "competition": "friendly",
      "status": "scheduled",
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 2.2,
      "odds_draw": 3.3,
      "odds_away": 3.2,
      "prob_home": 0.45,
      "prob_draw": 0.3,
      "prob_away": 0.31,
      "kickoff_at": "2026-06-02T00:00:00Z"
    },
    {
      "match_id": "WARM-007",
      "date": "2026-06-04",
      "home_team": "France",
      "home_flag": "🇫",
      "away_team": "Ivory Coast",
      "away_flag": "🇨",
      "competition": "favorite",
      "status": "scheduled",
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 1.3,
      "odds_draw": 5.0,
      "odds_away": 10.0,
      "prob_home": 0.77,
      "prob_draw": 0.16,
      "prob_away": 0.07,
      "kickoff_at": "2026-06-04T00:00:00Z"
    },
    {
      "match_id": "WARM-008",
      "date": "2026-06-04",
      "home_team": "Iraq",
      "home_flag": "🇮",
      "away_team": "Spain",
      "away_flag": "🇪",
      "competition": "friendly",
      "status": "scheduled",
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 12.0,
      "odds_draw": 6.0,
      "odds_away": 1.2,
      "prob_home": 0.08,
      "prob_draw": 0.12,
      "prob_away": 0.8,
      "kickoff_at": "2026-06-04T00:00:00Z"
    },
    {
      "match_id": "WARM-009",
      "date": "2026-06-06",
      "home_team": "USA",
      "home_flag": "🇺",
      "away_team": "Germany",
      "away_flag": "🇩",
      "competition": "marquee",
      "status": "scheduled",
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 2.8,
      "odds_draw": 3.2,
      "odds_away": 2.5,
      "prob_home": 0.36,
      "prob_draw": 0.31,
      "prob_away": 0.4,
      "kickoff_at": "2026-06-06T00:00:00Z"
    },
    {
      "match_id": "WARM-010",
      "date": "2026-06-06",
      "home_team": "England",
      "home_flag": "🏴",
      "away_team": "New Zealand",
      "away_flag": "🇳",
      "competition": "friendly",
      "status": "scheduled",
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:03:25Z",
      "confidence": 0.5,
      "odds_home": 1.1,
      "odds_draw": 8.0,
      "odds_away": 20.0,
      "prob_home": 0.91,
      "prob_draw": 0.07,
      "prob_away": 0.02,
      "kickoff_at": "2026-06-06T00:00:00Z"
    }
  ]
}

## 赛果状态摘要
{
  "version": "p10.0",
  "date": "2026-06-03",
  "provider": "legacy_seed",
  "fetched_at": "2026-06-03T14:04:08Z",
  "source_policy": "legacy_seed_no_external_fetch",
  "summary": {
    "total": 21,
    "finished": 3,
    "scheduled": 18,
    "missing_or_not_finished": 18
  },
  "results": [
    {
      "match_id": "WARM-001",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-002",
      "status": "settled",
      "home_score": 6,
      "away_score": 2,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-003",
      "status": "settled",
      "home_score": 3,
      "away_score": 2,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-004",
      "status": "settled",
      "home_score": 4,
      "away_score": 0,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-005",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-006",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-007",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-008",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-009",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-010",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-011",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-012",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WARM-013",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider": "legacy_seed",
      "source_url": "",
      "fetched_at": "2026-06-03T14:04:08Z",
      "confidence": 0.5,
      "result_state": "missing_or_not_finished",
      "extra_time": null,
      "penalties": null
    },
    {
      "match_id": "WC-A1",
      "status": "scheduled",
      "home_score": null,
      "away_score": null,
      "halftime_score": null,
      "red_cards": [],
      "injury_notes": [],
      "provider":
...<truncated>

## 赔率快照摘要
{
  "snapshot_label": "T-1h",
  "provider": "manual_stub",
  "summary": {
    "matches_total": 21,
    "markets_requested": [
      "moneyline",
      "handicap",
      "total_goals"
    ],
    "odds_rows": 147,
    "valid_odds_rows": 0,
    "missing_market_coverage": 63,
    "match_mapping_failed": 0,
    "provider_unavailable": false
  },
  "warning": "If valid_odds_rows is 0, do not invent odds. Use empty bet_ledger."
}

## 当前排行榜/账户摘要
{
  "version": "p9.2",
  "updated_at": "2026-06-03T19:30:00Z",
  "leaderboard": [
    {
      "model_account": "deepseek",
      "display_name": "DeepSeek",
      "rank": 1,
      "balance_gp": 2810,
      "loan_gp": 1000,
      "status": "active",
      "notes": "Run#4 三线命中，Run#5 有效回收"
    },
    {
      "model_account": "gemini",
      "display_name": "Gemini",
      "rank": 2,
      "balance_gp": 1850,
      "loan_gp": 1000,
      "status": "active",
      "notes": "Run#4 有效；Run#5 有效，上调 xG 基线"
    },
    {
      "model_account": "qwen",
      "display_name": "通义",
      "rank": 3,
      "balance_gp": 1500,
      "loan_gp": 400,
      "status": "active",
      "notes": "Run#4 有效；Run#5 有效"
    },
    {
      "model_account": "doubao",
      "display_name": "豆包",
      "rank": 4,
      "balance_gp": 1400,
      "loan_gp": 300,
      "status": "active",
      "notes": "Run#4 重仓 Brazil -1.5 命中；Run#5 有效"
    },
    {
      "model_account": "yuanbao",
      "display_name": "元宝",
      "rank": 5,
      "balance_gp": 1500,
      "loan_gp": 500,
      "status": "active",
      "notes": "Run#4 有效；Run#5 有效"
    },
    {
      "model_account": "mimo",
      "display_name": "MiMo",
      "rank": 6,
      "balance_gp": 1200,
      "loan_gp": 300,
      "status": "active",
      "notes": "Run#4 有效；Run#5 有效"
    },
    {
      "model_account": "meta",
      "display_name": "Meta AI",
      "rank": 7,
      "balance_gp": 1400,
      "loan_gp": 800,
      "status": "active",
      "notes": "Run#4 有效；Run#5 有效"
    },
    {
      "model_account": "claude",
      "display_name": "Claude",
      "rank": null,
      "balance_gp": null,
      "loan_gp": 300,
      "status": "audit_only",
      "notes": "Run#4 有效；Run#5 风险审计，不计入投注共识"
    },
    {
      "model_account": "chatgpt",
      "display_name": "ChatGPT",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "needs_rerun_context_polluted",
      "notes": "Run#5 上下文污染，需补跑"
    },
    {
      "model_account": "kimi",
      "display_name": "Kimi",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "needs_rerun_placeholder",
      "notes": "Run#5 占位输出，需补跑"
    },
    {
      "model_account": "wenxin",
      "display_name": "文心",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "needs_rerun_placeholder",
      "notes": "Run#5 占位输出，需补跑"
    },
    {
      "model_account": "minimax",
      "display_name": "MiniMax",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "needs_rerun_placeholder",
      "notes": "Run#5 占位输出，需补跑"
    },
    {
      "model_account": "xai",
      "display_name": "xAI Grok",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "quota_blocked",
      "notes": "Run#4 缺席；Run#5 额度阻断"
    }
  ]
}

## 上一轮日报摘要
{
  "version": "p9.4",
  "date": "2026-06-03",
  "round_id": "run-5",
  "generated_at": "2026-06-03T15:15:34Z",
  "summary": {
    "headline": "Run #5 Daily Report — 7 valid outputs, 5 models need rerun, 4 data gaps",
    "status": "report_generated",
    "total_models": 13,
    "total_matches": 21,
    "rerun_queue_count": 5
  },
  "model_status_counts": {
    "valid_receipt": 7,
    "placeholder_only": 3,
    "context_polluted": 1,
    "quota_blocked": 1,
    "auth_blocked": 0,
    "timeout": 0,
    "parse_error": 0,
    "risk_refusal": 1,
    "excluded_from_consensus": 6
  },
  "model_status_rows": [
    {
      "model_account": "gemini",
      "seat_id": "gemini",
      "status": "valid_receipt",
      "eligible_for_consensus": true,
      "needs_rerun": false,
      "failure_reason": "",
      "pollution_signals": []
    },
    {
      "model_account": "chatgpt",
      "seat_id": "chatgpt",
      "status": "context_polluted",
      "eligible_for_consensus": false,
      "needs_rerun": true,
      "failure_reason": "Detected legacy/werewolf context pollution",
      "pollution_signals": [
        "警长"
      ]
    },
    {
      "model_account": "claude",
      "seat_id": "claude",
      "status": "risk_refusal",
      "eligible_for_consensus": false,
      "needs_rerun": false,
      "failure_reason": "Risk/compliance refusal — audit only",
      "pollution_signals": []
    },
    {
      "model_account": "yuanbao",
      "seat_id": "yuanbao",
      "status": "valid_receipt",
      "eligible_for_consensus": true,
      "needs_rerun": false,
      "failure_reason": "",
      "pollution_signals": []
    },
    {
      "model_account": "wenxin",
      "seat_id": "wenxin",
      "status": "placeholder_only",
      "eligible_for_consensus": false,
      "needs_rerun": true,
      "failure_reason": "Output is placeholder only",
      "pollution_signals": []
    },
    {
      "model_account": "deepseek",
      "seat_id": "deepseek",
      "status": "valid_receipt",
      "eligible_for_consensus": true,
      "needs_rerun": false,
      "failure_reason": "",
      "pollution_signals": []
    },
    {
      "model_account": "mimo",
      "seat_id": "mimo",
      "status": "valid_receipt",
      "eligible_for_consensus": true,
      "needs_rerun": false,
      "failure_reason": "",
      "pollution_signals": []
    },
    {
      "model_account": "kimi",
      "seat_id": "kimi",
      "status": "placeholder_only",
      "eligible_for_consensus": false,
      "needs_rerun": true,
      "failure_reason": "Output is placeholder only",
      "pollution_signals": []
    },
    {
      "model_account": "qwen",
      "seat_id": "qwen",
      "status": "valid_receipt",
      "eligible_for_consensus": true,
      "needs_rerun": false,
      "failure_reason": "",
      "pollution_signals": []
    },
    {
      "model_account": "xai",
      "seat_id": "xai",
      "status": "quota_blocked",
      "eligible_for_consensus": false,
      "needs_rerun": true,
      "failure_reason": "Quota/rate limit blocked",
      "pollution_signals": []
    },
    {
      "model_account": "minimax",
      "seat_id": "minimax",
      "status": "placeholder_only",
      "eligible_for_consensus": false,
      "needs_rerun": true,
      "failure_reason": "Output is placeholder only",
      "pollution_signals": []
    },
    {
      "model_account": "doubao",
      "seat_id": "doubao",
      "status": "valid_receipt",
      "eligible_for_consensus": true,
      "needs_rerun": false,
      "failure_reason": "",
      "pollution_signals": []
    },
    {
      "model_account": "meta",
      "seat_id": "meta",
      "status": "valid_receipt",
      "eligible_for_consensus": true,
      "needs_rerun": false,
      "failure_reason": "",
      "pollution_signals": []
    }
  ],
  "rerun_queue": [
    {
      "model_account": "chatgpt",
      "seat_id": "chatgpt",
      "current_status": "context_polluted",
      "reason": "Detected legacy/werewolf context pollution",
      "attempt_no": 1,
      "next_attempt_no": 2,
      "priority": "high"
    },
    {
      "model_account": "wenxin",
      "seat_id": "wenxin",
      "current_status": "placeholder_only",
      "reason": "Output is placeholder only",
      "attempt_no": 1,
      "next_attempt_no": 2,
      "priority": "medium"
    },
    {
      "model_account": "kimi",
      "seat_id": "kimi",
      "current_status": "placeholder_only",
      "reason": "Output is placeholder only",
      "attempt_no": 1,
      "next_attempt_no": 2,
      "priority": "medium"
    },
    {
      "model_account": "xai",
      "seat_id": "xai",
      "current_status": "quota_blocked",
      "reason": "Quota/rate limit blocked",
      "attempt_no": 1,
      "next_attempt_no": 2,
      "priority": "high"
    },
    {
      "model_account": "minimax",
      "seat_id": "minimax",
      "current_status": "placeholder_only",
      "reason": "Output is placeholder only",
      "attempt_no": 1,
      "next_attempt_no": 2,
      "priority": "medium"
    }
  ],
  "consensus_eligibility": {
    "eligible_count": 7,
    "eligible_models": [
      "gemini",
      "yuanbao",
      "deepseek",
      "mimo",
      "qwen",
      "doubao",
      "meta"
    ],
    "excluded_count": 6,
    "excluded_models": [
      {
        "model_account": "chatgpt",
        "status": "context_polluted",
        "reason": "Detected legacy/werewolf context pollution"
      },
      {
        "model_account": "claude",
        "status": "risk_refusal",
        "reason": "Risk/compliance refusal — audit only"
      },
      {
        "model_account": "wenxin",
        "status": "placeholder_only",
        "reason": "Output is placeholder only"
      },
      {
        "model_account": "kimi",
        "status": "placeholder_only",
        "reason": "Output is placeholder only"
      },
      {
        "model_account": "xai",
        "status": "quota_blocked",
        "reason": "Quota/rate limit blocked"
      },
      {
        "model_a
...<truncated>

## 标准 JSON schema 示例
{
  "model_account": "qwen",
  "round_id": "run-6",
  "loan_decision": {
    "amount": 0,
    "reason": ""
  },
  "bet_ledger": [
    {
      "match_id": "WARM-002",
      "market": "moneyline",
      "selection": "Brazil",
      "stake": 100,
      "odds": 1.85,
      "confidence": 0.6,
      "reason": "",
      "cancel_if": ""
    }
  ],
  "risk_rules": {
    "max_loss": 500,
    "stop_after_losses": 2
  },
  "source_cards": [],
  "betting_thought": ""
}

## 如果没有有效赔率或没有可下注机会，必须输出以下结构
{
  "model_account": "qwen",
  "round_id": "run-6",
  "loan_decision": {
    "amount": 0,
    "reason": "No valid odds available."
  },
  "bet_ledger": [],
  "risk_rules": {
    "max_loss": 0,
    "stop_after_losses": 0
  },
  "source_cards": [],
  "betting_thought": "No valid bet because odds snapshot has no valid market coverage."
}

【强制输出格式】
你必须只输出一个 JSON 对象。
JSON 顶层必须包含：
- model_account
- round_id
- loan_decision
- bet_ledger
- risk_rules
- source_cards
- betting_thought

禁止输出任何 JSON 之外的内容。