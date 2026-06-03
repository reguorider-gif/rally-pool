# AI Judge 预测池事故处理手册

本文档定义常见事故场景及标准处理流程。

---

## 1. GitHub remote 404

### 现象

```bash
$ git push
remote: Repository not found.
fatal: repository 'https://github.com/reguorider/rally-pool.git/' not found
```

### 影响

- GitHub Actions 无法 checkout 和 commit
- 无法自动部署
- 本地开发不受影响

### 处理步骤

**Step 1：确认当前 remote 配置**

```bash
git remote -v
# 输出示例：
# origin  https://github.com/reguorider/rally-pool.git (fetch)
# origin  https://github.com/reguorider/rally-pool.git (push)
```

**Step 2：测试远程连接**

```bash
git ls-remote origin
```

如果返回 "Repository not found"，进入 Step 3。

**Step 3：修正 remote URL 或创建仓库**

选项 A — 修正 remote URL（确认仓库名和 owner 正确）：

```bash
git remote set-url origin https://github.com/<correct-owner>/<correct-repo>.git
```

选项 B — 在 GitHub 上创建新仓库后关联：

```bash
# 在 GitHub 创建仓库 rally-pool（不初始化 README）
git remote set-url origin https://github.com/<owner>/rally-pool.git
git push -u origin main
```

**Step 4：验证修复**

```bash
git push -u origin main
```

### 当前状态

- 已知残留（2026-06-04），不阻塞开发
- Pipeline 脚本和本地运行均正常
- 一旦 remote 恢复，GitHub Actions 即可自动运行

---

## 2. Vercel deployment failed

### 现象

```bash
$ vercel --prod
Error! Deployment failed.
```

### 影响

- 线上 API 和前端不会更新到最新版本
- 现有部署不受影响（上一个成功的 deployment 继续运行）

### 处理步骤

**Step 1：确认 Vercel 登录状态**

```bash
vercel whoami
vercel projects ls
```

**Step 2：检查环境变量**

```bash
vercel env ls
```

关键变量：
- `VERCEL_TOKEN`：个人访问令牌（https://vercel.com/account/tokens）
- `VERCEL_ORG_ID`：组织 ID（.vercel/project.json 或 Vercel 项目设置）
- `VERCEL_PROJECT_ID`：项目 ID（.vercel/project.json 或 Vercel 项目设置）

**Step 3：检查项目链接**

```bash
vercel link
```

**Step 4：重试部署**

```bash
vercel --prod
```

**Step 5：检查部署日志**

Vercel Dashboard → 项目 → Deployments → 查看失败 deployment 的 build log。

### 常见原因

- Token 过期：重新生成 VERCEL_TOKEN
- 项目未链接：`vercel link` 重新链接
- 构建失败：检查 `vercel.json` 和 Python 依赖
- 配额耗尽：联系 Vercel support

### Vercel 回滚

如果新部署导致问题，执行回滚：

1. Vercel Dashboard → Deployments
2. 找到上一个成功的 deployment
3. 点击 "..." → "Promote to Production"

---

## 3. GitHub Actions failed

### 现象

GitHub Actions workflow run 显示 ❌ failed。

### 影响

- 当日 pipeline 未执行
- `data/pool/` 文件未更新
- 可能需要手动补跑

### 处理步骤

**Step 1：检查 workflow logs**

在 GitHub Actions → 失败的 run → 展开每个 step 查看错误。

**Step 2：本地复现**

```bash
cd /path/to/pool-app
python3 ops/check_pool_data_health.py
python3 ops/validate_pool_schemas.py
```

**Step 3：手动运行 pipeline**

```bash
python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --skip-browser
```

**Step 4：检查是否为 warning 误判**

如果 pipeline `final_status = pass_with_warnings`，检查：
- 是否有步骤被 `--continue-on-warning` 跳过
- 是否有步骤因 upstream blocked 而 skipped
- 是否因为 `waiting_for_manual_ingest` 导致下游步骤跳过

**Step 5：检查生成文件**

```bash
ls -la data/pool/pipeline_runs/
cat data/pool/pipeline_runs/2026-06-03_run-6.json | python3 -m json.tool
```

### 常见原因

- Python 依赖缺失：检查 workflow 中的 `pip install` 步骤
- 文件路径错误：检查 DATA_DIR 和 ROOT_DIR 配置
- 超时：pipeline 步骤超过 GitHub Actions 默认超时时间
- warning 被误判为 failure：检查 `final_status` 逻辑

---

## 4. JSON 文件损坏

### 现象

```bash
$ python3 ops/check_pool_data_health.py
  ❌ data/pool/some_file.json: JSON parse error
```

### 影响

- 前端相关页面可能不可用
- API 返回 fallback 空结构（不崩溃）

### 处理步骤

**Step 1：确认哪个文件损坏**

```bash
python3 -m json.tool data/pool/<corrupted-file>.json
```

如果有解析错误，会显示具体行号和问题。

**Step 2：从 Git 恢复**

```bash
git checkout -- data/pool/<corrupted-file>.json
```

**Step 3：如果没有 Git history，重新生成**

```bash
# 根据文件类型选择相应操作
# 例如：重新运行 pipeline 生成
python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --skip-browser
```

**Step 4：验证修复**

```bash
python3 -m json.tool data/pool/<corrupted-file>.json
python3 ops/check_pool_data_health.py
```

### 预防

- 定期运行 `check_pool_data_health.py`
- 在 GitHub Actions 中先 validate 再 commit
- 不要手动编辑 data/pool/ 下的 JSON 文件

---

## 5. Pipeline waiting_for_manual_ingest

### 现象

Pipeline run 显示 ingest step 为 `skipped`，原因为 `waiting_for_manual_ingest`。

### 影响

- run-6 的 13 个模型输出未标准化
- 下游 classify/validate/settle/rerun steps 全部 skipped
- 这是**正常 warning，不是故障**

### 处理步骤

**Step 1：确认是否为 waiting_for_manual_ingest**

```bash
python3 -m json.tool data/pool/pipeline_runs/2026-06-03_run-6.json | grep -A5 ingest
```

输出应包含：
```json
"status": "skipped",
"reason": "waiting_for_manual_ingest — 模型输出未投喂"
```

**Step 2：准备模型输出**

将 13 个模型的原始输出放入：

```bash
data/pool/model_outputs/raw/run-6/<model_name>.txt
```

每个文件命名格式：`<model_name>.txt`（例如 `chatgpt.txt`、`claude.txt`）

**Step 3：执行 ingest**

```bash
python3 ops/ai_judge_daily_pool.py ingest \
  --round run-6 \
  --input-dir data/pool/model_outputs/raw/run-6
```

**Step 4：重新运行 pipeline（从 ingest 步骤开始）**

```bash
python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --skip-browser --continue-on-warning
```

ingest 之后的步骤（classify/validate/settle/rerun/daily_report）会自动运行。

### 当前状态

- run-6 的 13 个模型输出正在等待人工投喂
- 这是设计上的 feature，不是 bug
- ingest 完成后系统即可恢复正常流程

---

## 6. Odds snapshot 无有效赔率

### 现象

```bash
$ python3 ops/check_pool_data_health.py
  ✅ summary.matches_total = 21
  ✅ odds rows: 147, valid_odds_rows: 0
  ✅ manual_stub odds=null and status=missing_market_coverage
```

### 影响

- 当前 accepted_bets = 0（无真实赔率无法投注）
- 结算状态为 no_bets_to_settle
- 这是**正常状态（manual_stub 下是预期）**

### 处理步骤

**Step 1：确认当前 provider**

```bash
python3 -m json.tool data/pool/odds_snapshots/2026-06-03_T-1h.json | grep provider
```

当前为 `manual_stub`，所有 odds 为 null，confidence=0.0。

**Step 2：配置真实赔率源（可选）**

获取 THE_ODDS_API_KEY 后：

```bash
THE_ODDS_API_KEY=<your-key> python3 ops/sync_odds_snapshots.py \
  --date 2026-06-03 \
  --snapshot-label T-1h \
  --provider the_odds_api
```

### 禁止操作

- **不得**把 manual_stub 改成有效赔率（这是假数据）
- **不得**把 null odds 改成 0 或任意数值
- **不得**手动编辑 odds_snapshots 文件

---

## 7. 前端页面不可用

### 现象

访问 Vercel URL 返回错误或白屏。

### 影响

- 用户无法查看预测池数据
- 通常不影响后端数据生成

### 处理步骤

**Step 1：确认 Vercel 部署状态**

```bash
vercel projects ls
```

**Step 2：检查 API 端点**

```bash
curl -s https://<vercel-url>/api/pool/models | head
curl -s https://<vercel-url>/api/pool/pipeline-runs | head
curl -s https://<vercel-url>/api/cron/pipeline-status | head
```

**Step 3：检查浏览器 Console**

打开开发者工具，查看 JavaScript 错误。

**Step 4：回滚部署**

按照"Vercel deployment failed"章节的回滚步骤操作。

**Step 5：重新部署**

```bash
vercel --prod
```

---

## 8. `accepted_bets=0` 误解

### 常见误解

"accepted_bets=0 说明模型预测没有价值" / "盈利为 0"

### 正确理解

`accepted_bets=0` 的原因是：
1. `manual_stub` 提供者下 odds=null（无真实赔率数据）
2. `validate_model_outputs.py` 要求投注单必须有 valid odds
3. 所有模型的投注单被拒收（reason: `no_structured_bet_receipt` 或 `model_not_eligible_for_consensus`）

这不是"盈利为 0"，而是"无可投注"。profit 和 ROI 应该是 null，保持为 null。

### 解决方案

配置真实赔率源（THE_ODDS_API_KEY），使 odds_snapshots 包含 valid odds。

---

## 未覆盖场景

如遇到本文档未覆盖的事故，按以下顺序排查：

1. 运行 `python3 ops/check_pool_data_health.py` — 检查数据完整性
2. 运行 `python3 ops/check_ops_readiness.py` — 检查运维就绪状态
3. 查看 `data/pool/pipeline_runs/` — 检查最近 pipeline 状态
4. 查看 `data/pool/daily_reports/` — 检查最近 daily report
5. 查看 Vercel deployment logs
6. 查看 GitHub Actions workflow logs
