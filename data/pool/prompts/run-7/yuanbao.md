AI_JUDGE_RUN_MARKER:POOL_RUN-7_20260603

# AI Judge 赛事预测池独立模型席位

seat_id: yuanbao
model_account: yuanbao
display_name: 元宝
round_id: run-7
date: 2026-06-03

【合规与实验边界】
这是虚拟 GP 预测研究，不涉及真钱下注，不构成现实博彩建议。
所有投注均为模拟，仅用于算法研究与模型评估。

## 当前任务
你是 AI Judge 赛事预测池中的一个独立模型席位。
你必须基于给定 eligible_board、赛果状态、资金/风控约束，输出 P15 单一 JSON 投注单。
本轮有一个 Banker Judge（虚拟庄家/法官）在管理比赛池：它会根据排行榜、当前筹码、昨日营收、贷款额度和风控规则评估你的表现。
你的目标是在合规的虚拟 GP 研究范围内提升排名；如果排名压力需要，可以申请虚拟贷款，但必须说明贷款用途、预期回报和止损规则。
你还必须主动补充赛事资讯来源到 source_cards，例如伤停、首发、赛程密度、赔率异动、主客场、天气、新闻或统计页；不要把空 source_cards 当作默认答案。

## 强制防污染要求
- 不要回答旧任务。
- 不要回答狼人杀、警长投票、守卫、平民、预言家等无关任务。
- 不要输出 Markdown。
- 不要输出解释性自然语言。
- 不要输出 JSON 之外的任何内容。
- JSON 必须能被 json.loads 解析。
- 只能从 eligible_board 中选择下注对象。
- 每条 bets 必须引用 eligible_board 内现有的 board_id。
- odds_row_id 可选；如果省略，系统只允许从 board_id 解析。
- 不得自由编写不存在于 eligible_board 的比赛、盘口或赔率。
- 不得把 fallback match 写入 settlement bet。
- 下注 market / selection 必须与 board row 一致；你不需要重复填写 market/selection，validator 会从 board_id 解析。
- 如果没有合适下注，bets 必须为空，并填写 no_bet_reason。

## Provider-covered eligible_board（唯一可下注来源）
{
  "summary": {
    "eligible_board_rows": 989,
    "markets": [
      "handicap",
      "moneyline",
      "total_goals"
    ],
    "matches_covered": 5,
    "match_ids": [
      "WC-A1",
      "WC-F1",
      "WC-F2",
      "WC-H1",
      "WC-I1"
    ],
    "valid_for_settlement": true
  },
  "items": [
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_Mexico_1xBet_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_Mexico_1xBet_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "Mexico",
      "price": 2.21,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "1xBet",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_Mexico_BetOnline.ag_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_Mexico_BetOnline.ag_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "Mexico",
      "price": 1.71,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "BetOnline.ag",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_Mexico_Bovada_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_Mexico_Bovada_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "Mexico",
      "price": 2.0,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Bovada",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_Mexico_GTbets_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_Mexico_GTbets_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "Mexico",
      "price": 2.29,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "GTbets",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_Mexico_MyBookie.ag_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_Mexico_MyBookie.ag_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "Mexico",
      "price": 2.18,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "MyBookie.ag",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_Mexico_Pinnacle_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_Mexico_Pinnacle_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "Mexico",
      "price": 2.05,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Pinnacle",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_South Africa_1xBet_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_South Africa_1xBet_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "South Africa",
      "price": 1.59,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "1xBet",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_South Africa_BetOnline.ag_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_South Africa_BetOnline.ag_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "South Africa",
      "price": 2.2,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "BetOnline.ag",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_South Africa_Bovada_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_South Africa_Bovada_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "South Africa",
      "price": 1.83,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Bovada",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_South Africa_GTbets_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_South Africa_GTbets_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "South Africa",
      "price": 1.62,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "GTbets",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_South Africa_MyBookie.ag_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_South Africa_MyBookie.ag_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "South Africa",
      "price": 1.61,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "MyBookie.ag",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_handicap_South Africa_Pinnacle_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_handicap_South Africa_Pinnacle_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "handicap",
      "selection": "South Africa",
      "price": 1.86,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Pinnacle",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_1xBet_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_1xBet_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.55,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "1xBet",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_888sport_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_888sport_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.0,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "888sport",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Bet Right_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Bet Right_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.0,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Bet Right",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Bet Victor_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Bet Victor_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.33,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Bet Victor",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_BetMGM_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_BetMGM_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.33,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "BetMGM",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_BetOnline.ag_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_BetOnline.ag_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.65,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "BetOnline.ag",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_BetRivers_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_BetRivers_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.4,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "BetRivers",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Betclic (FR)_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Betclic (FR)_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.5,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Betclic (FR)",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Betfair_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Betfair_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.8,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Betfair",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Betfair_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Betfair_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.8,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Betfair",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Betfair_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Betfair_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.8,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Betfair",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Betfred (UK)_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Betfred (UK)_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.2,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Betfred (UK)",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Betr_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Betr_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.2,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Betr",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Betsson_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Betsson_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.45,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Betsson",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Betway_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Betway_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.2,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Betway",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Bovada_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Bovada_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.5,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "Bovada",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_BoyleSports_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_BoyleSports_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Africa",
      "commence_time": "2026-06-11T00:00:00Z",
      "market": "moneyline",
      "selection": "Draw",
      "price": 4.2,
      "last_update": "2026-06-04T06:45:46Z",
      "bookmaker_or_provider": "BoyleSports",
      "valid_for_settlement": true
    },
    {
      "board_id": "run-7:WC-A1_T-1h_moneyline_Draw_Casumo_the_odds_api",
      "provider": "the_odds_api",
      "provider_snapshot_id": "2026-06-03_T-1h_the_odds_api",
      "odds_row_id": "WC-A1_T-1h_moneyline_Draw_Casumo_the_odds_api",
      "match_id": "WC-A1",
      "home_team": "Mexico",
      "away_team": "South Afri
...<truncated>

## 赛果状态摘要
{
  "version": "p10.0",
  "date": "2026-06-03",
  "provider": "legacy_seed",
  "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
      "fetched_at": "2026-06-04T17:16:58Z",
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
  "provider": "the_odds_api",
  "summary": {
    "matches_total": 21,
    "markets_requested": [
      "moneyline",
      "handicap",
      "total_goals"
    ],
    "odds_rows": 1190,
    "valid_odds_rows": 989,
    "missing_market_coverage": 0,
    "match_mapping_failed": 201,
    "provider_unavailable": false,
    "provider_responded": true,
    "matched_internal_matches": 5,
    "coverage_status": "real_odds_provider_has_valid_odds"
  },
  "warning": "Do not bet from this snapshot directly. Use eligible_board rows only."
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
      "model_account": "chatgpt",
      "display_name": "ChatGPT",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "active",
      "notes": "Run#6 有效回收"
    },
    {
      "model_account": "kimi",
      "display_name": "Kimi",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "active",
      "notes": "Run#6 有效回收"
    },
    {
      "model_account": "wenxin",
      "display_name": "文心",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "active",
      "notes": "Run#6 有效回收"
    },
    {
      "model_account": "minimax",
      "display_name": "MiniMax",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "active",
      "notes": "Run#6 有效回收"
    },
    {
      "model_account": "xai",
      "display_name": "xAI Grok",
      "rank": null,
      "balance_gp": null,
      "loan_gp": null,
      "status": "active",
      "notes": "Run#6 有效回收"
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
  "seat_id": "yuanbao",
  "round_id": "run-7",
  "bets": [
    {
      "board_id": "run-7:EXAMPLE_PROVIDER_ODDS_ROW_ID",
      "stake_gp": 100,
      "rationale": "Board row selected from eligible_board only; market and selection match the provider row.",
      "risk": "Cancel or reduce if lineup, injury, weather, or odds movement invalidates the edge."
    }
  ],
  "no_bet_reason": null,
  "sources_checked": []
}

## 如果没有 provider-covered 可下注机会，必须输出以下结构
{
  "seat_id": "yuanbao",
  "round_id": "run-7",
  "bets": [],
  "no_bet_reason": "No provider-covered board row has positive expected value.",
  "sources_checked": []
}

【强制输出格式】
你必须只输出一个 JSON 对象。
JSON 顶层必须包含：
- seat_id
- round_id
- bets
- no_bet_reason
- sources_checked

bets 规则：
- accepted 结算只认 provider-covered board row。
- 每条 bets 必须包含 board_id；缺失会被 rejected_missing_provider_odds 拒收。
- 可选 odds_row_id；如果填写，必须与 board_id 对应行一致。
- stake_gp 必须为正数。
- market、selection、odds 必须由 eligible_board 行决定，不要自由改写。
- 不要写 fallback、manual_stub 或模型自造 odds。

禁止输出任何 JSON 之外的内容。