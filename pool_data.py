"""
pool_data.py — AI Judge 预测池统一数据加载层
P9.2 新增：从 data/pool/ 读取 JSON，提供安全读取函数。
"""

from pathlib import Path
import json
import sys

# 定位项目根目录（兼容 Vercel serverless 和本地运行）
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data" / "pool"

# ---------- 工具函数 ----------

def _read_json(relative_path, default=None):
    """
    安全读取 data/pool/ 下的 JSON 文件。
    - 文件不存在：返回 default（不抛异常）
    - JSON 解析失败：打印 warning，返回 default
    """
    full_path = DATA_DIR / relative_path
    if not full_path.exists():
        print(f"[pool_data] WARNING: file not found: {full_path}", file=sys.stderr)
        return default
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[pool_data] WARNING: JSON parse error in {full_path}: {e}", file=sys.stderr)
        return default
    except Exception as e:
        print(f"[pool_data] WARNING: failed to read {full_path}: {e}", file=sys.stderr)
        return default


def _write_json(relative_path, data, indent=2):
    """安全写入 JSON 到 data/pool/ 下。"""
    full_path = DATA_DIR / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


# ---------- 公开读取函数 ----------

def get_model_accounts():
    """
    返回 data/pool/model_accounts/current.json 中的 models 列表。
    失败时返回空结构 {"version":"", "models": []}。
    """
    data = _read_json("model_accounts/current.json", default=None)
    if data and "models" in data:
        return data
    # fallback：返回空结构，不崩溃
    return {"version": "fallback", "updated_at": "", "models": []}


def get_leaderboard():
    """
    P9.2.1 修复：从 data/pool/leaderboard/current.json 读取榜单数据。
    返回格式：{"version": "p9.2", "updated_at": "", "leaderboard": [...], "models": [...]}
    """
    return _read_json(
        "leaderboard/current.json",
        default={"version": "p9.2", "updated_at": "", "leaderboard": [], "models": []}
    )


def get_archives_index():
    """返回 data/pool/archives/index.json。"""
    return _read_json("archives/index.json", default={"version": "p9.2", "rounds": []})


def get_archive(round_id: str):
    """
    根据 round_id 读取对应的 archive JSON。
    例如 round_id="run-4" → data/pool/archives/run-4.json
    """
    filename = f"{round_id}.json"
    return _read_json(f"archives/{filename}", default=None)


def get_matches():
    """返回 data/pool/matches/current.json。"""
    return _read_json("matches/current.json", default=None)


def get_frontend_archives():
    """返回 data/pool/app_static/frontend_archives.json。"""
    return _read_json("app_static/frontend_archives.json", default=None)


# ---------- P9.2 新增：/api/pool/* 数据函数 ----------
# 以下函数在 P9.2 新增 API 时被 server.py / app.py 调用

def get_model_runs(round_id: str = None):
    """
    P9.3 实现：返回模型运行记录。
    - 传 round_id → 读取 data/pool/model_runs/{round_id}.json
    - 不传 → 返回所有可用 model_runs 摘要
    - 文件不存在 → 返回空结构
    """
    if round_id:
        data = _read_json(f"model_runs/{round_id}.json", default=None)
        if data:
            return data
        return {
            "version": "p9.3",
            "round_id": round_id,
            "generated_at": "",
            "summary": {"total": 0},
            "runs": [],
        }
    # 不传 round_id：扫描 model_runs 目录
    mr_dir = DATA_DIR / "model_runs"
    if not mr_dir.exists():
        return {"version": "p9.3", "available_rounds": []}
    rounds = []
    for f in sorted(mr_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            rounds.append({
                "round_id": d.get("round_id", f.stem),
                "total": d.get("summary", {}).get("total", 0),
                "generated_at": d.get("generated_at", ""),
            })
        except Exception:
            rounds.append({"round_id": f.stem, "total": 0, "generated_at": ""})
    return {"version": "p9.3", "available_rounds": rounds}


def get_model_outputs(round_id: str = None):
    """
    P9.3 新增：返回模型原始输出记录。
    - 传 round_id → 读取 data/pool/model_outputs/{round_id}.json
    - 不传 → 返回所有可用 model_outputs 摘要
    - 文件不存在 → 返回空结构
    """
    if round_id:
        data = _read_json(f"model_outputs/{round_id}.json", default=None)
        if data:
            return data
        return {
            "version": "p9.3",
            "round_id": round_id,
            "generated_at": "",
            "outputs": [],
        }
    # 不传 round_id：扫描 model_outputs 目录
    mo_dir = DATA_DIR / "model_outputs"
    if not mo_dir.exists():
        return {"version": "p9.3", "available_rounds": []}
    rounds = []
    for f in sorted(mo_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            rounds.append({
                "round_id": d.get("round_id", f.stem),
                "output_count": len(d.get("outputs", [])),
                "generated_at": d.get("generated_at", ""),
            })
        except Exception:
            rounds.append({"round_id": f.stem, "output_count": 0, "generated_at": ""})
    return {"version": "p9.3", "available_rounds": rounds}


def get_rerun_queue(round_id: str = None):
    """
    P9.3 新增：返回补跑队列。
    - 传 round_id → 读取 data/pool/rerun_queue/{round_id}.json
    - 不传 → 返回所有可用 rerun_queue 摘要
    - 文件不存在 → 返回空结构
    """
    if round_id:
        data = _read_json(f"rerun_queue/{round_id}.json", default=None)
        if data:
            return data
        return {
            "version": "p9.3",
            "round_id": round_id,
            "generated_at": "",
            "max_attempts": 3,
            "queue": [],
        }
    # 不传 round_id：扫描 rerun_queue 目录
    rq_dir = DATA_DIR / "rerun_queue"
    if not rq_dir.exists():
        return {"version": "p9.3", "available_rounds": []}
    rounds = []
    for f in sorted(rq_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            rounds.append({
                "round_id": d.get("round_id", f.stem),
                "queue_count": len(d.get("queue", [])),
                "generated_at": d.get("generated_at", ""),
            })
        except Exception:
            rounds.append({"round_id": f.stem, "queue_count": 0, "generated_at": ""})
    return {"version": "p9.3", "available_rounds": rounds}


def get_model_health():
    """
    P9.2 占位：返回模型健康状态。
    """
    # TODO P9.3: 实际从 data/pool/model_health/current.json 读取
    return {"updated_at": "", "models": []}


def get_daily_reports():
    """
    P9.4 实现：返回 data/pool/daily_reports/ 下的报告摘要列表。
    无参数：扫描目录，返回 available_reports 列表。
    文件不存在：返回空结构，不崩溃。
    """
    dr_dir = DATA_DIR / "daily_reports"
    if not dr_dir.exists():
        return {"version": "p9.4", "updated_at": "", "available_reports": []}
    reports = []
    for f in sorted(dr_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            reports.append({
                "date":      d.get("date", ""),
                "round_id":  d.get("round_id", ""),
                "generated_at": d.get("generated_at", ""),
                "headline":  d.get("summary", {}).get("headline", ""),
                "file":       f.name,
            })
        except Exception:
            reports.append({"date": "", "round_id": f.stem, "file": f.name})
    return {"version": "p9.4", "updated_at": "", "available_reports": reports}


def get_daily_report(date: str = None, round_id: str = None):
    """
    P9.4 实现：返回单个日报的完整 JSON。
    - 传 date + round_id → 读取 data/pool/daily_reports/{date}_{round_id}.json
    - 不传 → 返回空结构
    - 文件不存在 → 返回空结构，不崩溃
    """
    if not date or not round_id:
        return {
            "version":    "p9.4",
            "date":       "",
            "round_id":   "",
            "generated_at": "",
            "summary":    {},
            "model_status_counts": {},
            "model_status_rows":   [],
            "rerun_queue":        [],
            "consensus_eligibility": {"eligible_count": 0, "eligible_models": [], "excluded_count": 0, "excluded_models": []},
            "risk_summary":       {"total_stake": None, "max_single_match_risk": None, "loan_used": None, "status": "missing"},
            "data_gaps":          [],
            "next_actions":       [],
            "generated_files":    [],
            "source_files":       [],
        }
    filename = f"{date}_{round_id}.json"
    data = _read_json(f"daily_reports/{filename}", default=None)
    if data:
        return data
    # 文件不存在，返回空结构
    return {
        "version":    "p9.4",
        "date":       date,
        "round_id":   round_id,
        "generated_at": "",
        "summary":    {"headline": "", "status": "not_found", "total_models": 0, "total_matches": 0, "rerun_queue_count": 0},
        "model_status_counts": {},
        "model_status_rows":   [],
        "rerun_queue":        [],
        "consensus_eligibility": {"eligible_count": 0, "eligible_models": [], "excluded_count": 0, "excluded_models": []},
        "risk_summary":       {"total_stake": None, "max_single_match_risk": None, "loan_used": None, "status": "not_found"},
        "data_gaps":          [],
        "next_actions":       [],
        "generated_files":    [],
        "source_files":       [],
    }


def get_match_results(date: str = None):
    """
    P10.0 实现：返回指定日期的赛果文件。
    - 传 date → 读取 data/pool/match_results/{date}.json
    - 不传 → 返回可用日期列表
    - 文件不存在 → 返回空结构，不崩溃
    """
    mr_dir = DATA_DIR / "match_results"
    if date is None:
        if not mr_dir.exists():
            return {"version": "p10.0", "available_dates": []}
        dates = sorted([f.stem for f in mr_dir.glob("*.json")], reverse=True)
        return {"version": "p10.0", "available_dates": dates}
    # Specific date
    data = _read_json(f"match_results/{date}.json", default=None)
    if data:
        return data
    return {
        "version":       "p10.0",
        "date":          date,
        "provider":      "",
        "fetched_at":    "",
        "source_policy": "",
        "summary":       {"total": 0, "finished": 0, "scheduled": 0, "missing_or_not_finished": 0},
        "results":       [],
    }


def get_match_result(date: str = None, match_id: str = None):
    """
    P10.0 实现：返回单场比赛结果。
    - 传 date + match_id → 从 match_results 中查找单场
    - 文件不存在 → 返回空结构，不崩溃
    """
    if not date or not match_id:
        return {"match_id": "", "status": "scheduled", "result_state": "missing_or_not_finished"}
    results_data = get_match_results(date)
    for r in results_data.get("results", []):
        if r.get("match_id") == match_id:
            return r
    return {
        "match_id":     match_id,
        "status":       "scheduled",
        "home_score":   None,
        "away_score":   None,
        "halftime_score": None,
        "red_cards":    [],
        "injury_notes": [],
        "provider":     "",
        "source_url":   "",
        "fetched_at":   "",
        "confidence":   0.5,
        "result_state": "missing_or_not_finished",
        "extra_time":   None,
        "penalties":    None,
    }


def get_match_snapshots():
    """
    P10.0 实现：返回 matches/snapshots/ 下的可用快照列表。
    """
    snap_dir = DATA_DIR / "matches" / "snapshots"
    if not snap_dir.exists():
        return {"version": "p10.0", "available_snapshots": []}
    snapshots = sorted([f.stem for f in snap_dir.glob("*.json")], reverse=True)
    return {"version": "p10.0", "available_snapshots": snapshots}


def get_odds_snapshots(date: str = None, snapshot_label: str = None):
    """
    P10.1 实现：返回赔率快照索引或指定快照列表。
    - 无参数        → 读取 data/pool/odds_snapshots/index.json
    - 只传 date    → 返回该日期所有快照（从 index 中过滤）
    - date+label    → 读取 data/pool/odds_snapshots/{date}_{label}.json
    - 文件不存在   → 返回空结构，不崩溃
    """
    idx_path = DATA_DIR / "odds_snapshots" / "index.json"
    if date is None and snapshot_label is None:
        data = _read_json("odds_snapshots/index.json", default=None)
        if data:
            return data
        return {"version": "p10.1", "updated_at": "", "snapshots": []}

    if date and snapshot_label:
        fname = f"{date}_{snapshot_label}.json"
        data = _read_json(f"odds_snapshots/{fname}", default=None)
        if data:
            return data
        return {
            "version":       "p10.1",
            "date":          date,
            "snapshot_label": snapshot_label,
            "missing":       True,
            "error":         "odds snapshot not found",
            "odds":          [],
        }

    # Only date: filter index for that date
    idx = _read_json("odds_snapshots/index.json", default=None)
    if idx and "snapshots" in idx:
        filtered = [s for s in idx["snapshots"] if s.get("date") == date]
        return {"date": date, "snapshots": filtered}

    return {"date": date, "snapshots": []}


def get_odds_snapshot(date: str = None, snapshot_label: str = None):
    """
    P10.1 实现：返回单个赔率快照完整内容。
    - 传 date + snapshot_label → 读取单个快照文件
    - 文件不存在 → 返回空结构，不崩溃
    """
    if not date or not snapshot_label:
        return {"missing": True, "error": "date and snapshot_label required"}
    fname = f"{date}_{snapshot_label}.json"
    data = _read_json(f"odds_snapshots/{fname}", default=None)
    if data:
        return data
    return {
        "version":       "p10.1",
        "date":          date,
        "snapshot_label": snapshot_label,
        "missing":       True,
        "error":         "odds snapshot not found",
        "odds":          [],
    }


# ────────── P10.2 Bet Receipts ───────────────────────────────────────────────

def get_bet_receipts(round_id: str = None):
    """
    P10.2 实现：返回投注单数据。
    - 无 round_id → 返回 index.json
    - 有 round_id → 返回 data/pool/bet_receipts/{round_id}.json
    - 文件不存在 → 返回 missing 结构，不崩溃
    """
    idx_path = "bet_receipts/index.json"
    if round_id is None:
        data = _read_json(idx_path, default=None)
        if data:
            return data
        return {"version": "p10.2", "updated_at": "", "rounds": []}

    fname = f"bet_receipts/{round_id}.json"
    data = _read_json(fname, default=None)
    if data:
        return data
    return {
        "version": "p10.2",
        "round_id": round_id,
        "missing": True,
        "error": "bet receipts not found",
        "accepted_receipts": [],
    }


def get_bet_receipt(round_id: str = None):
    """
    P10.2 实现：获取单个 round 的完整投注单。
    与 get_bet_receipts(round_id) 相同，提供更具语义的别名。
    """
    if not round_id:
        return {"missing": True, "error": "round_id required"}
    return get_bet_receipts(round_id=round_id)


def get_bet_rejections(round_id: str = None):
    """
    P10.2 实现：获取投注拒收记录。
    - 有 round_id → 返回 data/pool/bet_receipts/rejections/{round_id}.json
    - 文件不存在 → 返回 missing 结构，不崩溃
    """
    if not round_id:
        return {"missing": True, "error": "round_id required"}
    fname = f"bet_receipts/rejections/{round_id}.json"
    data = _read_json(fname, default=None)
    if data:
        return data
    return {
        "version": "p10.2",
        "round_id": round_id,
        "missing": True,
        "error": "bet rejections not found",
        "rejections": [],
    }


# ---------- 数据健康检查（供 ops/check_pool_data_health.py 调用） ----------

def check_data_health():
    """
    检查 data/pool/ 下关键文件的存在性和 JSON 有效性。
    返回列表，每项：{"path": ..., "exists": bool, "valid_json": bool, "record_count": int, "warning": str}
    """
    results = []
    checks = [
        ("model_accounts/current.json",        lambda d: len(d.get("models", []))),
        ("matches/current.json",        lambda d: len(d.get("matches", []))),
        ("archives/index.json",        lambda d: len(d.get("rounds", []))),
        ("archives/run-4.json",       lambda d: 1),
        ("archives/run-5.json",       lambda d: 1),
        ("app_static/frontend_archives.json", lambda d: 1),
    ]
    for rel_path, count_fn in checks:
        item = {"path": f"data/pool/{rel_path}", "exists": False, "valid_json": False, "record_count": 0, "warning": ""}
        data = _read_json(rel_path, default=None)
        if data is None:
            item["warning"] = "file not found or unreadable"
        else:
            item["exists"] = True
            item["valid_json"] = True
            try:
                item["record_count"] = count_fn(data)
            except Exception:
                item["record_count"] = 0
                item["warning"] = "count function failed"
        results.append(item)
    return results
