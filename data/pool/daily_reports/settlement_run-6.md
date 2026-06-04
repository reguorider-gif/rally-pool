# AI Judge 赛事预测池结算报告 — run-6

## 1. 结算结论

本轮 **accepted_bets=0**，因此没有可结算投注。

- **settlement_status**: `manual_review`
- **valid_for_leaderboard_update**: `False`
- **profit/ROI 不应计算为 0**，而应标记为 null / not_applicable。

## 2. Bet Receipt 摘要

- **models_total**: 12
- **accepted_bets**: 3
- **rejected_bets**: 11
- **valid_for_settlement**: True

## 3. Rejection 摘要

? rejections

## 4. 结算结果

| 项目 | 值 |
|---|---|
| settlement_status | manual_review |
| accepted_bets | 3 |
| settled_bets | 0 |
| total_profit | None |
| roi | None |
| valid_for_leaderboard_update | False |
| winning_bets | 0 |
| losing_bets | 0 |
| void_bets | 0 |
| push_bets | 0 |
| manual_review_bets | 3 |

## 5. 为什么没有 ROI

本轮 accepted_bets=0，因此没有可结算投注。

profit 和 ROI 不应计算为 0，而应标记为 **null** / **not_applicable**。

原因：没有下注 → 0 收益不等于结算为 0。标记为 null 可防止后续排行榜误解读。

## 6. 下一步动作

- **settlement_not_implemented**: Settlement logic for accepted_bets > 0 is not yet implemented. All bets moved to manual_review.

- 等待补跑完成后，重新运行 validate_model_outputs.py 生成有 structured receipts 的投注单。
- 配置真实赔率源（the_odds_api），使 odds snapshots 有有效赔率行。
- 重新运行 settle_pool_round.py 进行真实结算。

## 7. 来源文件

- `data/pool/bet_receipts/run-6.json`
- `data/pool/bet_receipts/rejections/run-6.json`
- `data/pool/bet_receipts/index.json`
- `data/pool/match_results/2026-06-03.json`
- `data/pool/odds_snapshots/2026-06-03_T-1h.json`
- `data/pool/leaderboard/current.json`
- `data/pool/model_accounts/current.json`

---
*生成时间: 2026-06-04T10:26:22Z*
*版本: p10.3*
