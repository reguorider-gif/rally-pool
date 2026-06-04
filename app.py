"""
AI Judge 预测池 Web 服务
启动：python app.py → http://localhost:8080
部署：vercel --prod → https://rally-pool.vercel.app

P9.2 新增：/api/pool/* 扩展接口，优先从 pool_data.py 读取 JSON 数据。
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path
import uvicorn
import sys
import json

# 优先从 server.py 导入原有函数
from server import (
    init, get_leaderboard, get_matches, get_match_predictions,
    get_seat_predictions, get_seat_loans, get_daily_logs,
    get_match_dates, get_stats, get_round_archives, get_round_archive
)

# P9.2 新增：尝试导入 pool_data 数据加载层
try:
    from pool_data import (
        get_model_accounts, get_archives_index, get_archive as pd_get_archive,
        get_matches as pd_get_matches, get_frontend_archives,
        get_model_runs, get_model_outputs, get_rerun_queue,
        get_model_health, get_daily_reports, get_daily_report, get_odds_snapshots, get_odds_snapshot,
        get_match_results, get_match_result, get_match_snapshots,
        get_bet_receipts, get_bet_receipt, get_bet_rejections,
        get_settlement_readiness,
        get_settlements, get_settlement,
        get_run_manifests, get_run_manifest, get_ingested_outputs,
        get_rerun_attempts, get_rerun_attempt, get_ingested_rerun_outputs,
        check_data_health,
        get_pipeline_runs, get_pipeline_run,
        get_latest_pipeline_run, get_latest_daily_report,
        get_ops_readiness,
        get_provider_status, get_odds_snapshots as pd_get_odds_snapshots, get_odds_snapshot as pd_get_odds_snapshot,
        get_provider_smoke, get_output_dropbox_report,
        get_runtime_summary,
    )
    _HAS_POOL_API = True
    print("[app.py] pool_data loaded successfully")
except Exception as _e:
    print(f"[app.py] WARNING: pool_data not available: {_e}", file=sys.stderr)
    _HAS_POOL_API = False

app = FastAPI(title="AI Judge Prediction Pool")
HTML_DIR = Path(__file__).parent / "html"

# Vercel serverless: 每次冷启动时初始化数据库
_initialized = False

def ensure_init():
    global _initialized
    if not _initialized:
        init()
        _initialized = True

# === API 路由 ===

@app.get("/api/stats")
def api_stats():
    ensure_init()
    return get_stats()

@app.get("/api/leaderboard")
def api_leaderboard():
    ensure_init()
    return get_leaderboard()

@app.get("/api/matches")
def api_matches(date: str = None):
    ensure_init()
    return get_matches(date)

@app.get("/api/match-dates")
def api_match_dates():
    ensure_init()
    return get_match_dates()

@app.get("/api/match/{match_id}/predictions")
def api_match_predictions(match_id: str):
    ensure_init()
    return get_match_predictions(match_id)

@app.get("/api/seat/{seat_id}")
def api_seat(seat_id: str):
    ensure_init()
    predictions = get_seat_predictions(seat_id)
    loans = get_seat_loans(seat_id)
    return {"predictions": predictions, "loans": loans}

@app.get("/api/daily-logs")
def api_daily_logs():
    ensure_init()
    return get_daily_logs()

@app.get("/api/archives")
def api_archives():
    ensure_init()
    return get_round_archives()


@app.get("/api/archive/{round_id}")
def api_archive(round_id: str):
    ensure_init()
    return get_round_archive(round_id)

# === P9.2 新增：/api/pool/* 扩展接口 ===

@app.get("/api/pool/runs")
def api_pool_runs():
    """返回 Run #4 / Run #5 档案索引"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_archives_index()
        except Exception as e:
            print(f"[api_pool_runs] pool_data failed: {e}", file=sys.stderr)
    # fallback：从 SQLite 读取
    return get_round_archives()


@app.get("/api/pool/runs/{round_id}")
def api_pool_run_detail(round_id: str):
    """返回某轮次完整档案（含 packets + sources）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            data = pd_get_archive(round_id)
            if data:
                return data
        except Exception as e:
            print(f"[api_pool_run_detail] pool_data failed: {e}", file=sys.stderr)
    # fallback：从 SQLite 读取
    return get_round_archive(round_id)


@app.get("/api/pool/model-runs")
def api_pool_model_runs(round_id: str = None):
    """返回模型运行记录（P9.3 升级：从 pool_data 读取）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_model_runs(round_id)
        except Exception as e:
            print(f"[api_pool_model_runs] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "runs": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/model-runs/{round_id}")
def api_pool_model_runs_detail(round_id: str):
    """返回指定轮次的模型运行记录"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_model_runs(round_id)
        except Exception as e:
            print(f"[api_pool_model_runs_detail] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "runs": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/model-outputs")
def api_pool_model_outputs(round_id: str = None):
    """返回模型原始输出记录（P9.3 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_model_outputs(round_id)
        except Exception as e:
            print(f"[api_pool_model_outputs] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "outputs": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/model-outputs/{round_id}")
def api_pool_model_outputs_detail(round_id: str):
    """返回指定轮次的模型原始输出"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_model_outputs(round_id)
        except Exception as e:
            print(f"[api_pool_model_outputs_detail] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "outputs": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/rerun-queue")
def api_pool_rerun_queue(round_id: str = None):
    """返回补跑队列（P9.3 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_rerun_queue(round_id)
        except Exception as e:
            print(f"[api_pool_rerun_queue] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "queue": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/rerun-queue/{round_id}")
def api_pool_rerun_queue_detail(round_id: str):
    """返回指定轮次的补跑队列"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_rerun_queue(round_id)
        except Exception as e:
            print(f"[api_pool_rerun_queue_detail] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "queue": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/model-health")
def api_pool_model_health():
    """返回模型健康状态"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_model_health()
        except Exception as e:
            print(f"[api_pool_model_health] pool_data failed: {e}", file=sys.stderr)
    return {"models": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/odds-snapshots")
async def api_pool_odds_snapshots():
    """返回赔率快照索引（P10.1 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_odds_snapshots()
        except Exception as e:
            print(f"[api_pool_odds_snapshots] pool_data failed: {e}", file=sys.stderr)
    return {"version": "p10.1", "updated_at": "", "snapshots": []}


@app.get("/api/pool/odds-snapshots/{date}")
async def api_pool_odds_snapshots_by_date(date: str):
    """返回指定日期的全部赔率快照（P10.1 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_odds_snapshots(date=date)
        except Exception as e:
            print(f"[api_pool_odds_snapshots_by_date] pool_data failed: {e}", file=sys.stderr)
    return {"date": date, "snapshots": []}


@app.get("/api/pool/odds-snapshots/{date}/{snapshot_label}")
async def api_pool_odds_snapshot(date: str, snapshot_label: str, provider: str = None):
    """返回单个赔率快照（P10.1 新增，P13.0 增强支持 provider）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_odds_snapshot(date=date, snapshot_label=snapshot_label, provider=provider)
        except Exception as e:
            print(f"[api_pool_odds_snapshot] pool_data failed: {e}", file=sys.stderr)
    return {"date": date, "snapshot_label": snapshot_label, "odds": [], "warning": "pool_data unavailable"}


# --- P13.0 Provider-specific Odds Snapshot API ---

@app.get("/api/pool/odds-snapshots/{date}/{snapshot_label}/{provider}")
async def api_pool_odds_snapshot_by_provider(date: str, snapshot_label: str, provider: str):
    """返回指定 provider 的赔率快照（P13.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_odds_snapshot(date=date, snapshot_label=snapshot_label, provider=provider)
        except Exception as e:
            print(f"[api_pool_odds_snapshot_by_provider] pool_data failed: {e}", file=sys.stderr)
    return {"date": date, "snapshot_label": snapshot_label, "provider": provider,
            "odds": [], "warning": "pool_data unavailable"}


# --- P13.0 Provider Status API ---

@app.get("/api/pool/provider-status")
async def api_pool_provider_status():
    """返回赔率供应商配置状态（P13.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_provider_status()
        except Exception as e:
            print(f"[api_pool_provider_status] pool_data failed: {e}", file=sys.stderr)
    from datetime import datetime, timezone
    return {
        "version":       "p13.0",
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "overall":        "unavailable",
        "providers":     [],
        "blockers":      [],
        "warnings":      ["pool_data unavailable"],
    }


# --- P13.0 Provider Smoke Test API ---

@app.get("/api/pool/provider-smoke/{round_id}/{date}")
async def api_pool_provider_smoke(round_id: str, date: str):
    """返回真实赔率源 smoke test 结果（P13.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_provider_smoke(round_id=round_id, date=date)
        except Exception as e:
            print(f"[api_pool_provider_smoke] pool_data failed: {e}", file=sys.stderr)
    from datetime import datetime, timezone
    return {
        "version":     "p13.0",
        "round_id":    round_id,
        "date":        date,
        "status":      "BLOCKED_PROVIDER_NOT_CONFIGURED",
        "summary": {
            "provider":           "the_odds_api",
            "configured":         False,
            "provider_responded": None,
            "matched_internal_matches": 0,
            "valid_odds_rows":   0,
            "coverage_status":   "real_odds_provider_not_configured",
        },
        "blocks": [],
        "warnings":  ["THE_ODDS_API_KEY is not set"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --- P13.0 Model Output Dropbox API ---

@app.get("/api/pool/output-dropbox/{round_id}")
async def api_pool_output_dropbox(round_id: str):
    """返回模型输出投喂目录状态（P13.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_output_dropbox_report(round_id=round_id)
        except Exception as e:
            print(f"[api_pool_output_dropbox] pool_data failed: {e}", file=sys.stderr)
    # 读取 dropbox_check.json
    dropbox_path = Path("data/pool/model_outputs/raw") / round_id / "dropbox_check.json"
    if dropbox_path.exists():
        try:
            with open(dropbox_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[api_pool_output_dropbox] failed to read {dropbox_path}: {e}", file=sys.stderr)
    # 返回默认值
    from datetime import datetime, timezone
    return {
        "version":          "p13.0",
        "round_id":         round_id,
        "status":           "waiting_for_manual_ingest",
        "outputs_expected": 12,
        "outputs_found":    0,
        "outputs_missing":  12,
        "missing_models":   [],
        "empty_files":     [],
        "invalid_names":   [],
        "has_run_marker":  False,
        "has_round_id":    False,
        "details":          {},
        "generated_at":    datetime.now(timezone.utc).isoformat(),
    }


# --- P10.2 Bet Receipts API ---

@app.get("/api/pool/bet-receipts")
async def api_pool_bet_receipts():
    """返回投注单索引（P10.2 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_bet_receipts()
        except Exception as e:
            print(f"[api_pool_bet_receipts] pool_data failed: {e}", file=sys.stderr)
    return {"version": "p10.2", "updated_at": "", "rounds": []}


@app.get("/api/pool/bet-receipts/{round_id}")
async def api_pool_bet_receipt(round_id: str):
    """返回单个 round 的投注单（P10.2 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_bet_receipt(round_id=round_id)
        except Exception as e:
            print(f"[api_pool_bet_receipt] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "accepted_receipts": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/bet-rejections/{round_id}")
async def api_pool_bet_rejections(round_id: str):
    """返回投注拒收记录（P10.2 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_bet_rejections(round_id=round_id)
        except Exception as e:
            print(f"[api_pool_bet_rejections] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "rejections": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/settlement-readiness/{round_id}")
async def api_pool_settlement_readiness(round_id: str):
    """返回 P14 provider-covered settlement readiness 红绿灯。"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_settlement_readiness(round_id=round_id)
        except Exception as e:
            print(f"[api_pool_settlement_readiness] pool_data failed: {e}", file=sys.stderr)
    return {
        "version": "p14.0",
        "run_id": round_id,
        "round_id": round_id,
        "eligible_board_rows": 0,
        "accepted_bets": 0,
        "provider_covered_accepted_bets": 0,
        "fallback_bets": 0,
        "analysis_only_bets": 0,
        "valid_for_settlement": False,
        "blockers": ["pool_data unavailable"],
    }


# --- P10.3 Settlements API ---

@app.get("/api/pool/settlements")
async def api_pool_settlements():
    """返回结算索引（P10.3 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_settlements()
        except Exception as e:
            print(f"[api_pool_settlements] pool_data failed: {e}", file=sys.stderr)
    return {"version": "p10.3", "updated_at": "", "rounds": []}


@app.get("/api/pool/settlements/{round_id}")
async def api_pool_settlement(round_id: str):
    """返回单个 round 的结算结果（P10.3 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_settlement(round_id=round_id)
        except Exception as e:
            print(f"[api_pool_settlement] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "settlement_status": "missing", "warning": "pool_data unavailable"}


# --- P11.0 Run Manifests & Ingested Outputs API ---

@app.get("/api/pool/run-manifests")
async def api_pool_run_manifests():
    """返回所有 run manifest 索引（P11.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_run_manifests()
        except Exception as e:
            print(f"[api_pool_run_manifests] pool_data failed: {e}", file=sys.stderr)
    return {"version": "p11.0", "updated_at": "", "rounds": []}


@app.get("/api/pool/run-manifests/{round_id}")
async def api_pool_run_manifest(round_id: str):
    """返回单个 run manifest（P11.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_run_manifest(round_id=round_id)
        except Exception as e:
            print(f"[api_pool_run_manifest] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "missing": True, "warning": "pool_data unavailable"}


@app.get("/api/pool/ingested-outputs/{round_id}")
async def api_pool_ingested_outputs(round_id: str):
    """返回 ingest 后的标准化输出索引（P11.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_ingested_outputs(round_id=round_id)
        except Exception as e:
            print(f"[api_pool_ingested_outputs] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "missing": True, "warning": "pool_data unavailable"}


# --- P11.1 补跑机制 API ---

@app.get("/api/pool/rerun-attempts")
async def api_pool_rerun_attempts():
    """返回所有补跑 attempt ledger 索引（P11.1 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_rerun_attempts()
        except Exception as e:
            print(f"[api_pool_rerun_attempts] pool_data failed: {e}", file=sys.stderr)
    return {"version": "p11.1", "rounds": []}


@app.get("/api/pool/rerun-attempts/{round_id}")
async def api_pool_rerun_attempts_by_round(round_id: str):
    """返回单个 round 的补跑 attempt ledger（P11.1 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_rerun_attempt(round_id=round_id)
        except Exception as e:
            print(f"[api_pool_rerun_attempts_by_round] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "missing": True, "warning": "pool_data unavailable"}


@app.get("/api/pool/ingested-rerun-outputs/{round_id}/{attempt_no}")
async def api_pool_ingested_rerun_outputs(round_id: str, attempt_no: int):
    """返回补跑 ingest 后的标准化输出索引（P11.1 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_ingested_rerun_outputs(round_id=round_id, attempt_no=attempt_no)
        except Exception as e:
            print(f"[api_pool_ingested_rerun_outputs] pool_data failed: {e}", file=sys.stderr)
    return {"round_id": round_id, "attempt_no": attempt_no, "missing": True, "warning": "pool_data unavailable"}


@app.get("/api/pool/daily-reports")
def api_pool_daily_reports():
    """返回每日报告索引"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_daily_reports()
        except Exception as e:
            print(f"[api_pool_daily_reports] pool_data failed: {e}", file=sys.stderr)
    return {"reports": []}


@app.get("/api/pool/daily-reports/{date}/{round_id}")
async def api_pool_daily_report(date: str, round_id: str):
    """返回单个日报（P9.4 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_daily_report(date, round_id)
        except Exception as e:
            print(f"[api_pool_daily_report] pool_data failed: {e}", file=sys.stderr)
    return {"date": date, "round_id": round_id, "warning": "pool_data unavailable"}


# --- P10.0 Match Results & Snapshots ---

@app.get("/api/pool/match-results")
async def api_pool_match_results():
    """返回可用赛果日期列表（P10.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_match_results()
        except Exception as e:
            print(f"[api_match_results] pool_data failed: {e}", file=sys.stderr)
    return {"available_dates": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/match-results/{date}")
async def api_pool_match_results_date(date: str):
    """返回指定日期的全部赛果（P10.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_match_results(date)
        except Exception as e:
            print(f"[api_match_results_date] pool_data failed: {e}", file=sys.stderr)
    return {"date": date, "results": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/match-results/{date}/{match_id}")
async def api_pool_match_result_single(date: str, match_id: str):
    """返回单场比赛结果（P10.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_match_result(date, match_id)
        except Exception as e:
            print(f"[api_match_result_single] pool_data failed: {e}", file=sys.stderr)
    return {"match_id": match_id, "warning": "pool_data unavailable"}


@app.get("/api/pool/match-snapshots")
async def api_pool_match_snapshots():
    """返回可用的赛程快照日期列表（P10.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_match_snapshots()
        except Exception as e:
            print(f"[api_match_snapshots] pool_data failed: {e}", file=sys.stderr)
    return {"available_snapshots": [], "warning": "pool_data unavailable"}


@app.get("/api/pool/data-health")
def api_pool_data_health():
    """返回 data/pool/ 数据文件健康检查结果"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return {"status": "ok", "data_files": check_data_health()}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "pool_data_unavailable"}


# --- P12.2 Ops Readiness API ---

@app.get("/api/pool/ops-readiness")
def api_pool_ops_readiness():
    """返回运维就绪状态检查（P12.2 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_ops_readiness()
        except Exception as e:
            print(f"[api_pool_ops_readiness] pool_data failed: {e}", file=sys.stderr)
    return {
        "version": "p12.2",
        "overall_status": "unavailable",
        "missing": True,
        "error": "pool_data unavailable",
        "checks": [],
        "warnings": [],
        "blockers": [],
        "next_actions": [],
    }


@app.get("/api/pool/models")
def api_pool_models():
    """返回模型席位列表（来自 data/pool/model_accounts/current.json）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_model_accounts()
        except Exception as e:
            print(f"[api_pool_models] pool_data failed: {e}", file=sys.stderr)
    return {"version": "fallback", "models": []}


@app.get("/api/pool/frontend-archives")
def api_pool_frontend_archives():
    """返回前端归档数据（赛果、模型复盘等）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            data = get_frontend_archives()
            if data:
                return data
        except Exception as e:
            print(f"[api_pool_frontend_archives] pool_data failed: {e}", file=sys.stderr)
    return {"version": "p9.2", "round_results": [], "run4_model_archive": [], "run5_model_archive": [], "run4_source_tasks": [], "ucl_bets": []}


@app.get("/api/pool/runtime-summary")
def api_pool_runtime_summary(round_id: str = "run-7", date: str = "2026-06-03"):
    """返回预测池当前运行态与历史归档摘要。"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_runtime_summary(round_id=round_id, date=date)
        except Exception as e:
            print(f"[api_pool_runtime_summary] pool_data failed: {e}", file=sys.stderr)
    return {
        "version": "p14.0",
        "generated_at": "",
        "current_round": round_id,
        "date": date,
        "active_models_count": 0,
        "active_models": [],
        "current_ranking": [],
        "provider": {"overall": "unavailable", "valid_odds_rows": 0},
        "model_outputs": {"outputs_expected": 0, "outputs_found": 0, "outputs_missing": 0},
        "betting": {"accepted_bets": 0, "accepted_receipts": 0, "gap": True},
        "automation": {"pipeline_status": "unavailable", "data_gaps": [], "next_actions": []},
        "archives": {"counts": {}, "round_results": [], "ucl_bets": [], "run4_model_archive": [], "run5_model_archive": []},
    }


# --- P12.0 Pipeline Runs API ---

@app.get("/api/pool/pipeline-runs")
async def api_pool_pipeline_runs():
    """返回 pipeline run 摘要列表（P12.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_pipeline_runs()
        except Exception as e:
            print(f"[api_pool_pipeline_runs] pool_data failed: {e}", file=sys.stderr)
    return {"version": "p12.0", "updated_at": "", "pipeline_runs": []}


@app.get("/api/pool/pipeline-runs/{date}/{round_id}")
async def api_pool_pipeline_run(date: str, round_id: str):
    """返回单个 pipeline run 完整数据（P12.0 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_pipeline_run(date=date, round_id=round_id)
        except Exception as e:
            print(f"[api_pool_pipeline_run] pool_data failed: {e}", file=sys.stderr)
    return {"version": "p12.0", "date": date, "round_id": round_id, "missing": True, "pipeline_run": None, "warning": "pool_data unavailable"}


# --- P12.1 Vercel Cron Status Probe ---

@app.get("/api/cron/pipeline-status")
async def api_cron_pipeline_status():
    """
    Vercel Cron 轻量探针（P12.1 新增）。
    - 只读，不写任何文件
    - 不触发 pipeline
    - 不部署
    """
    ensure_init()
    # 读取最新 pipeline run
    try:
        latest = get_latest_pipeline_run()
        return {
            "status": "ok",
            "latest_pipeline_run": latest,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


# === HTML 页面 ===

@app.get("/", response_class=HTMLResponse)
def index():
    ensure_init()
    html_path = HTML_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"), media_type="text/html")
    return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
