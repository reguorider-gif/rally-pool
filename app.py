"""
AI Judge 预测池 Web 服务
启动：python app.py
访问：http://localhost:8080
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from server import (
    init, get_leaderboard, get_matches, get_match_predictions,
    get_seat_predictions, get_seat_loans, get_daily_logs,
    get_match_dates, get_stats
)

app = FastAPI(title="AI Judge Prediction Pool")
HTML_DIR = Path(__file__).parent / "html"

# === API 路由 ===

@app.get("/api/stats")
def api_stats():
    return get_stats()

@app.get("/api/leaderboard")
def api_leaderboard():
    return get_leaderboard()

@app.get("/api/matches")
def api_matches(date: str = None):
    return get_matches(date)

@app.get("/api/match-dates")
def api_match_dates():
    return get_match_dates()

@app.get("/api/match/{match_id}/predictions")
def api_match_predictions(match_id: str):
    return get_match_predictions(match_id)

@app.get("/api/seat/{seat_id}")
def api_seat(seat_id: str):
    predictions = get_seat_predictions(seat_id)
    loans = get_seat_loans(seat_id)
    return {"predictions": predictions, "loans": loans}

@app.get("/api/daily-logs")
def api_daily_logs():
    return get_daily_logs()

# === 前端页面 ===

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = HTML_DIR / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>AI Judge Prediction Pool</h1><p>Dashboard loading...</p>"

# === 启动 ===

if __name__ == "__main__":
    init()
    print("\n🚀 Starting AI Judge Prediction Pool...")
    print("📊 Dashboard: http://localhost:8080")
    print("📡 API: http://localhost:8080/api/stats")
    uvicorn.run(app, host="0.0.0.0", port=8080)
