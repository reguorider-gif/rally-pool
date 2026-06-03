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
        check_data_health,
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
async def api_pool_odds_snapshot(date: str, snapshot_label: str):
    """返回单个赔率快照（P10.1 新增）"""
    ensure_init()
    if _HAS_POOL_API:
        try:
            return get_odds_snapshot(date=date, snapshot_label=snapshot_label)
        except Exception as e:
            print(f"[api_pool_odds_snapshot] pool_data failed: {e}", file=sys.stderr)
    return {"date": date, "snapshot_label": snapshot_label, "odds": [], "warning": "pool_data unavailable"}


# ── P10.2 Bet Receipts API ──────────────────────────────────────────────────
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


# === 前端页面 ===

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = HTML_DIR / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>AI Judge Prediction Pool</h1><p>Dashboard loading...</p>"

# === 本地启动 ===

if __name__ == "__main__":
    ensure_init()
    print("\n🚀 Starting AI Judge Prediction Pool...")
    print("📊 Dashboard: http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
