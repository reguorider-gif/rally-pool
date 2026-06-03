# AI Judge 预测池告警策略

## 告警等级定义

| 等级 | 含义 | 响应时间 | 示例 |
|---|---|---|---|
| **P0** | 数据损坏 / 线上不可用 | 立即 | JSON parse fail、Vercel API 500、pipeline blocker |
| **P1** | 核心链路失败 | 1 小时内 | pipeline failed、health check fail、daily report missing |
| **P2** | 可恢复 warning | 24 小时内 | waiting_for_manual_ingest、manual_stub odds、no valid bets |
| **P3** | 信息提示 | 无需响应 | no file changes to commit、cron probe ok |

---

## Alert Rules（告警规则）

### P0 规则

| 规则 | 触发条件 | 影响 |
|---|---|---|
| `json_parse_failure` | 任何 `data/pool/` 下 JSON 文件无法解析 | 前端和数据 API 不可用 |
| `vercel_api_500` | `/api/pool/*` 任意端点返回 5xx | 线上服务不可用 |
| `pipeline_blocked` | `final_status = blocked` | 核心链路被阻塞，需要人工介入 |
| `data_corruption` | `check_pool_data_health` 报告 hard error | 关键数据文件丢失或格式错误 |

### P1 规则

| 规则 | 触发条件 | 影响 |
|---|---|---|
| `pipeline_failed` | `final_status = failed` | Pipeline 异常退出，当日数据可能不完整 |
| `health_check_failed` | `check_pool_data_health` 返回 has_error=True | 数据健康检查未通过 |
| `daily_report_missing` | 当日 `daily_reports/*.json` 不存在 | 缺少每日报告 |
| `cron_probe_non_200` | `/api/cron/pipeline-status` 返回非 200 | Cron 探针不可达，无法确认 pipeline 状态 |
| `pipeline_latest_missing` | `/api/pool/pipeline-runs` 无最新记录 | 最近一次 pipeline 未运行或记录丢失 |
| `github_remote_404` | GitHub 仓库不可达 | 无法 auto-commit pipeline 生成文件 |

### P2 规则（expected warnings）

| 规则 | 触发条件 | 说明 |
|---|---|---|
| `waiting_for_manual_ingest` | run-6 ingest state 为 waiting_for_manual_ingest | 需要人工投喂模型输出，不是故障 |
| `manual_stub_odds` | `valid_odds_rows = 0` 且 provider 为 manual_stub | 当前赔率为手动桩数据，预期状态 |
| `accepted_bets_zero` | `accepted_bets = 0` | manual_stub 无真实赔率导致，预期状态 |
| `settlement_no_bets` | `settlement_status = no_bets_to_settle` | accepted_bets=0 导致，预期状态 |
| `rerun_queue_pending` | `rerun_queue` 有待处理条目 | 有模型需要补跑，非 blocker |
| `ingest_missing_outputs` | `outputs_found=0` with `outputs_total>0` | 模型输出尚未投喂，预期在 waiting_for_manual_ingest 阶段 |
| `no_file_changes` | Pipeline 运行后无新文件产生 | 信息提示，可能是已是最新状态 |

### P3 规则

| 规则 | 触发条件 | 说明 |
|---|---|---|
| `cron_probe_ok` | `/api/cron/pipeline-status` 返回 200 且 ok=true | 定期确认探针正常 |
| `pipeline_pass_with_warnings` | `final_status = pass_with_warnings` | 有 P2 warning，但无 blocker |
| `pipeline_pass` | `final_status = pass` | 全部通过，无异常 |

---

## 告警响应矩阵

| 告警等级 | 通知方式 | 响应人 | 预期动作 |
|---|---|---|---|
| P0 | 即时通知（企微/邮件） | 值班人员 | 立即介入，恢复服务 |
| P1 | 通知 + issue 创建 | 值班人员 | 1 小时内排查 |
| P2 | 仅记录（不通知） | - | 下次 pipeline 运行时自动恢复或人工投喂 |
| P3 | 日志记录 | - | 无需响应 |

---

## 关键原则

### 不把 P2 warning 当成失败

- `waiting_for_manual_ingest` → 不是 pipeline bug，是需要人工投喂模型输出
- `accepted_bets = 0` → 不是盈利为 0，是 manual_stub 无真实赔率导致无法投注
- `no_bets_to_settle` → 不是结算故障，是没有可结算的投注
- `manual_stub odds=null` → 不是赔率损坏，是桩数据的设计特征

### 不把缺失数据自动补成假数据

- null profit → 保持 null，不改成 0
- null ROI → 保持 null，不改成 0
- missing model output → 不生成假输出
- manual_stub odds=null → 不改成虚假赔率

### P2 → P1 升级条件

以下情况 P2 warning 升级为 P1：
- `waiting_for_manual_ingest` 持续超过 7 天
- `accepted_bets = 0` 在配置真实赔率源后仍持续
- `rerun_queue` 累积超过 7 个条目

---

## 当前已知告警状态（2026-06-04）

| 规则 | 等级 | 状态 | 说明 |
|---|---|---|---|
| `waiting_for_manual_ingest` | P2 | 活跃 | run-6 等待模型输出投喂 |
| `manual_stub_odds` | P2 | 活跃 | 赔率为手动桩数据 |
| `accepted_bets_zero` | P2 | 活跃 | run-5 无可投注 |
| `settlement_no_bets` | P2 | 活跃 | run-5 无投注可结算 |
| `github_remote_404` | P1 | 活跃 | 远程仓库不可达 |
| `rerun_queue_pending` | P2 | 活跃 | run-5 有 5 个模型待补跑 |

---

## 告警渠道配置（待实现）

当前告警策略仅为文档定义，未接入实际告警渠道。后续可通过以下方式实现：
- GitHub Actions workflow 的 `if: failure()` 发送通知
- Vercel Cron 定期检查 → Webhook → 企微机器人
- 自定义监控脚本 + cron job
