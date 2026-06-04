# AI Judge 预测池日常操作 Checklist

当前生产 URL：`https://pool-app-one.vercel.app`

---

## 每日检查（Daily）

执行时间：每天 UTC 09:30 之后（北京时间 17:30 之后）

### Pipeline / Cron 状态

- [ ] `/api/cron/pipeline-status` 返回 200 OK
  ```bash
  curl -s https://<vercel-url>/api/cron/pipeline-status | python3 -m json.tool | head -20
  ```

- [ ] `/api/pool/pipeline-runs` 可读且有最新记录
  ```bash
  curl -s https://<vercel-url>/api/pool/pipeline-runs | python3 -m json.tool | head -10
  ```

- [ ] 最新 pipeline `final_status` 不是 `failed` 或 `blocked`
  ```bash
  python3 ops/check_ops_readiness.py
  ```

### 数据健康

- [ ] `check_pool_data_health.py` 输出 PASS（无 hard error）
  ```bash
  python3 ops/check_pool_data_health.py
  ```

### 前端

- [ ] 访问 `https://<vercel-url>` 五页可切换
  - Dashboard
  - Models
  - Match Detail
  - Run Archives
  - System Health

- [ ] 系统健康页无红色错误标记
  - 数据文件健康检查 ✅
  - API 连通性检查 200 OK
  - Pipeline Runs 显示最新状态
  - Scheduler / Deployment 显示正常
  - Operations Readiness 显示 ready

### 模型输出状态

- [ ] 若 `waiting_for_manual_ingest`，确认是否需要人工投喂

  如果是 run-6，检查 `data/pool/model_outputs/ingested/run-6/index.json`：
  ```bash
  python3 -m json.tool data/pool/model_outputs/ingested/run-6/index.json
  ```

  如果需要投喂，执行：
  ```bash
  # 先把模型输出放入 data/pool/model_outputs/raw/run-6/<model>.txt
  python3 ops/ai_judge_daily_pool.py ingest --round run-6 --input-dir data/pool/model_outputs/raw/run-6
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --skip-browser --continue-on-warning
  ```

---

## 每周检查（Weekly）

执行时间：每周一 UTC 09:00（每周一北京时间 17:00）

### 调度器健康

- [ ] GitHub Actions schedule 是否正常触发
  - 上周是否有缺失的 workflow run？
  - GitHub Actions → AI Judge Daily Pool Pipeline → 查看 run history

- [ ] Vercel Cron 是否正常触发
  - 检查 Vercel Dashboard → 项目 → Cron Jobs
  - 确认 `/api/cron/pipeline-status` 有规律的调用记录

### 数据管理

- [ ] `data/pool/` 文件是否过度膨胀
  ```bash
  du -sh data/pool/
  du -sh data/pool/odds_snapshots/
  du -sh data/pool/pipeline_runs/
  du -sh data/pool/daily_reports/
  ```

  如果某个目录超过 100MB，考虑归档旧文件。

- [ ] `manual_stub` 是否仍是 odds provider
  ```bash
  python3 -m json.tool data/pool/odds_snapshots/2026-06-03_T-1h.json | grep provider
  ```

- [ ] 是否需要配置 `THE_ODDS_API_KEY`
  - 如果准备启用真实赔率，在 GitHub Secrets 或本地环境变量中添加

### 系统健康

- [ ] `check_ops_readiness.py` 输出 `overall_status` 为 `ready` 或 `ready_with_warnings`
  ```bash
  python3 ops/check_ops_readiness.py
  ```

- [ ] 告警检查 — 是否有新的 P1/P0 问题
  ```bash
  python3 ops/check_ops_readiness.py --json | python3 -m json.tool | grep -E "blockers|warnings"
  ```

### 代码质量

- [ ] 所有 Python 文件可编译
  ```bash
  PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile server.py app.py pool_data.py ops/*.py
  ```

---

## 发布前检查（Pre-release）

在每次代码变更部署前执行：

### 语法与静态检查

- [ ] py_compile 全部通过
  ```bash
  PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
    server.py app.py pool_data.py \
    ops/check_pool_data_health.py \
    ops/check_ops_readiness.py \
    ops/run_daily_pool_pipeline.py \
    ops/validate_pool_schemas.py
  ```

- [ ] `validate_pool_schemas.py` 通过
  ```bash
  python3 ops/validate_pool_schemas.py
  ```

### 数据健康

- [ ] `check_pool_data_health.py` PASS
  ```bash
  python3 ops/check_pool_data_health.py
  ```

### 运维就绪

- [ ] `check_ops_readiness.py` 通过（`ready` 或 `ready_with_warnings`）
  ```bash
  python3 ops/check_ops_readiness.py
  ```

### 部署

- [ ] Vercel 部署成功
  ```bash
  vercel --prod
  ```

### 线上验证

- [ ] 前端五页可切换
- [ ] API 端点可访问
  ```bash
  curl -s https://<vercel-url>/api/pool/models | python3 -m json.tool | head
  curl -s https://<vercel-url>/api/cron/pipeline-status | python3 -m json.tool | head
  curl -s https://<vercel-url>/api/pool/ops-readiness | python3 -m json.tool | head
  ```

### 文档

- [ ] 生产文档（runbook/alerting/incident/checklist）存在且最新
- [ ] 若有新增/修改功能，更新对应文档

---

## 验收检查（Per-phase）

每个开发阶段（PXX）结束前执行：

```bash
# 1. 编译检查
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile server.py app.py pool_data.py ops/*.py

# 2. Schema 验证
python3 ops/validate_pool_schemas.py

# 3. 数据健康
python3 ops/check_pool_data_health.py

# 4. 运维就绪
python3 ops/check_ops_readiness.py

# 5. Pool data 离线验证
python3 -c "import pool_data; print('OK')"

# 6. Pipeline dry-run
python3 ops/run_daily_pool_pipeline.py --date $(date +%Y-%m-%d) --round run-6 --dry-run --skip-browser

# 7. Vercel 部署
vercel --prod

# 8. 线上 API 验证
curl -s https://<vercel-url>/api/pool/models | python3 -m json.tool | head
curl -s https://<vercel-url>/api/cron/pipeline-status | python3 -m json.tool | head
curl -s https://<vercel-url>/api/pool/ops-readiness | python3 -m json.tool | head

# 9. 前端验证：五页可切换、系统健康页无红色错误
```
