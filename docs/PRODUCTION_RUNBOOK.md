# AI Judge 赛事预测池生产运行手册

## 1. 系统职责

AI Judge 赛事预测池（Prediction Pool）是一个 AI 模型足球赛果预测系统，核心流程包括：

1. 赛事同步（sync_matches）
2. 赛果同步（sync_results）
3. 赔率快照采集（sync_odds_snapshots）
4. 生成模型提示词（generate_prompts）
5. 模型输出投喂 & 标准化（ingest）
6. 模型输出分类（classify_model_output）
7. 投注单验证（validate_model_outputs）
8. 投注结算（settle_pool_round）
9. 补跑失败模型（rerun_failed_seats）
10. 每日报告生成（daily_report）
11. 数据健康检查（check_pool_data_health）

系统由 AI Judge Python 应用 + Vercel 静态托管 + GitHub Actions 调度组成。

---

## 2. 当前部署拓扑

| 组件 | 位置 | 角色 |
|---|---|---|
| **GitHub Actions** | `.github/workflows/daily-pool-pipeline.yml` | 主调度器，执行 pipeline、commit 生成文件、可选 Vercel 部署 |
| **Vercel** | `pool-app-one.vercel.app` | Web API + 前端托管，提供 `/api/pool/*` 和静态 HTML |
| **Vercel Cron** | `vercel.json` crons 配置 | 轻量探针，只读读取最新 pipeline 状态 |
| **本地 ops 脚本** | `ops/run_daily_pool_pipeline.py` | 开发者本地运行和调试 |
| **数据文件** | `data/pool/` | 所有预测池数据，包含 matches/odds/bets/settlements/reports 等 |

---

## 3. 每日运行流程

### 北京时间时间线

| 时间 | 事件 | 调度器 |
|---|---|---|
| 17:15 | Pipeline 执行（同步赛果、赔率、投注、结算、报告） | GitHub Actions |
| 17:15-17:20 | Commit + Push 生成文件到 repo | GitHub Actions |
| 17:20 | （可选）Vercel 部署 | GitHub Actions |
| 17:30 | 状态探针确认 pipeline 结果 | Vercel Cron |

### Pipeline 13 步流程

`ops/run_daily_pool_pipeline.py` 按顺序执行：

1. `preflight` — py_compile 预检
2. `sync_matches` — 同步赛事数据
3. `sync_results` — 同步赛果
4. `sync_odds_snapshots` — 采集赔率快照（当前 manual_stub）
5. `generate_prompts` — 生成模型提示词
6. `ingest` — 模型输出标准化投喂（当前 run-6 为 waiting_for_manual_ingest）
7. `classify` — 分类模型输出
8. `validate` — 投注单验证
9. `settle` — 结算
10. `rerun` — 补跑失败模型
11. `daily_report` — 生成每日报告
12. `health_check` — 数据健康检查
13. `deploy` — (可选) Vercel 部署

每一步都有独立状态（`pass`/`skipped`/`failed`/`blocked`），最终 `final_status` 为：
- `pass`：全部通过
- `pass_with_warnings`：有 warning 但无 blocker
- `blocked`：有 blocker
- `failed`：Pipeline 执行异常

---

## 4. 手动运行流程

### 本地完整 pipeline

```bash
cd /path/to/pool-app
python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --skip-browser
```

### 只看计划不执行

```bash
python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --dry-run
```

### 仅运行特定步骤

```bash
# 只看健康状态
python3 ops/check_pool_data_health.py
python3 ops/validate_pool_schemas.py

# 手动投喂模型输出
python3 ops/ai_judge_daily_pool.py ingest --round run-6 --input-dir data/pool/model_outputs/raw/run-6
```

### 手动部署 Vercel

```bash
vercel --prod
```

---

## 5. GitHub Actions 调度流程

文件：`.github/workflows/daily-pool-pipeline.yml`

### 触发方式

1. **定时**：`schedule: "15 9 * * *"` (UTC 09:15)
2. **手动**：Actions → AI Judge Daily Pool Pipeline → Run workflow
   - 可指定 `date`、`round`、`deploy`

### 执行步骤

```
Checkout → Setup Python → py_compile preflight → validate_schemas + health_check
→ run_daily_pool_pipeline.py --skip-browser --continue-on-warning
→ validate_schemas + health_check (post)
→ show pipeline summary
→ commit data/pool/ changes → push
→ (optional) vercel deploy
```

### 需要的 Secrets

| Secret | 必需 | 用途 |
|---|---|---|
| `VERCEL_TOKEN` | deploy=true | Vercel 个人 Token |
| `VERCEL_ORG_ID` | deploy=true | Vercel 组织 ID |
| `VERCEL_PROJECT_ID` | deploy=true | Vercel 项目 ID |
| `THE_ODDS_API_KEY` | 可选 | 体育赔率 API key |

当前状态：GitHub remote 404，Actions 尚未在线手动验证。

---

## 6. Vercel Cron 探针流程

### 端点

`GET /api/cron/pipeline-status`

### 行为

- 读取最新 pipeline run 状态
- 读取最新 daily report 状态
- 返回 JSON 状态摘要
- **不写文件、不触发 pipeline、不部署**
- 即使无 pipeline 也返回 `ok=true` + warning

### 调度

`vercel.json` crons: `"30 9 * * *"` (UTC 09:30，比 GH Actions 晚 15 分钟)

### 职责边界

| 能力 | GitHub Actions | Vercel Cron |
|---|---|---|
| 执行 Python 脚本 | ✅ | ❌ |
| 写 data/pool/ 文件 | ✅ | ❌ |
| Commit & Push | ✅ | ❌ |
| Vercel 部署 | ✅ (可选) | ❌ |
| 读取 pipeline 状态 | ✅ | ✅ |
| 状态告警 | ✅ | ✅ |
| 文件持久化 | ✅ (repo) | ❌ (serverless) |

---

## 7. 数据文件地图

```
data/pool/
├── model_accounts/current.json       # 13 个 AI 模型席位
├── leaderboard/current.json          # 榜单
├── matches/
│   ├── current.json                  # 当前 21 场比赛
│   └── snapshots/                    # 赛程快照
├── match_results/                    # 赛果
├── odds_snapshots/                   # 赔率快照 (manual_stub)
├── model_runs/                       # 模型运行记录
├── model_outputs/
│   ├── raw/                          # 原始模型输出
│   └── ingested/                     # 标准化后输出
├── run_manifests/                    # 赛轮描述文件
├── prompts/                          # 生成的提示词
├── bet_receipts/                     # 投注单
│   └── rejections/                   # 拒收记录
├── settlements/                      # 结算结果
├── rerun_queue/                      # 补跑队列
├── rerun_attempts/                   # 补跑尝试 ledger
├── daily_reports/                    # 每日报告
├── pipeline_runs/                    # Pipeline 运行记录
├── ops_readiness/                    # 运维就绪检查结果
├── archives/                         # 历史轮次归档
└── app_static/                       # 前端静态数据
```

---

## 8. 正常 warning 与 blocker 区分

### 正常 warning（不是故障）

| Warning | 含义 | 处理 |
|---|---|---|
| `waiting_for_manual_ingest` | 模型输出尚未人工投喂 | 投放模型输出后 ingest |
| `manual_stub odds` | 赔率为手动桩数据（无真实赔率） | 配置 THE_ODDS_API_KEY 后自动替换 |
| `accepted_bets = 0` | 无可投注（因为 manual_stub 无真实赔率） | 正常，等真实赔率 |
| `no_bets_to_settle` | 无投注可结算 | 正常，等 accepted_bets > 0 |
| `valid_odds_rows = 0` | 赔率行无有效数据 | manual_stub 下是预期 |
| GitHub remote 404 | 远程仓库不可达 | P1 运维警告，不阻塞开发 |
| `rerun_queue` 有条目 | 有待补跑模型 | 非 blocker，记录即可 |

### Blocker（真正的故障）

| Blocker | 含义 |
|---|---|
| JSON 文件解析失败 | `pool_data.py` 无法读取关键数据 |
| Vercel API 500 | 线上不可用 |
| `final_status = failed` | Pipeline 执行异常退出 |
| `final_status = blocked` | Pipeline 有 step 因数据缺失而 blocked |
| health check 失败 | 关键数据文件丢失或损坏 |
| `/api/cron/pipeline-status` 非 200 | Cron 探针不可达 |

### 重要原则

- **不把 warning 当 blocker**
- **不把 `accepted_bets=0` 当成盈利为 0**
- **不把 null profit / null ROI 改成 0**
- **不把 `manual_stub` 当真实赔率源**
- **不把 missing model output 自动补成假输出**

---

## 9. 常见故障恢复

详见 `docs/INCIDENT_PLAYBOOK.md`。

| 故障 | 恢复方式 |
|---|---|
| GitHub remote 404 | 检查 `git remote -v`，修正 URL 或创建仓库 |
| Vercel deployment failed | 检查 Token/Org ID/Project ID，`vercel --prod` |
| GitHub Actions failed | 检查 workflow logs，本地跑 health check |
| JSON 文件损坏 | `python3 -m json.tool <file>` 检查，`git checkout -- <file>` 恢复 |
| pipeline waiting_for_manual_ingest | 不是故障，投喂模型输出后 ingest |
| odds snapshot 无有效赔率 | manual_stub 下是预期，配置真实 API 后重跑 |

---

## 10. 发布与回滚

### 发布流程

```bash
# 1. 预检
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile server.py app.py pool_data.py
python3 ops/validate_pool_schemas.py
python3 ops/check_pool_data_health.py
python3 ops/check_ops_readiness.py

# 2. 提交
git add -A
git commit -m "PXX release notes"
git push

# 3. 部署
vercel --prod
```

### 回滚

```bash
# 回滚到上一个 commit
git revert HEAD
git push
vercel --prod

# 或回滚到指定 commit
git reset --hard <commit-hash>
git push --force
vercel --prod
```

### Vercel 回滚

Vercel Dashboard → Deployments → 选择上一个成功的 deployment → Promote to Production

---

## 11. 禁止操作

1. **不改业务数据语义**：不改动 model_outputs、bets、settlements 的数据结构
2. **不跑 AI Judge**：不在运维操作中触发模型推理
3. **不接真实赔率源**：除非明确配置 THE_ODDS_API_KEY
4. **不自动补跑**：不自动重跑失败的 pipeline step
5. **不生成假输出**：不伪造模型输出、赔率或赛果
6. **不把 warning 当 blocker**：告警和部署判断必须区分 P2 warning 和 P0/P1 blocker
7. **不隐藏 GitHub remote 404**：作为已知残留在文档中记录
8. **不提交 API key**：不在 commit 中包含 token/secret
9. **不删除现有 docs/data 文件**：不清理历史报告或归档
10. **不在文档中承诺 fully autonomous**：当前系统仍需人工投喂模型输出
