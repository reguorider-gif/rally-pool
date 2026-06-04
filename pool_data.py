"""
pool_data.py — AI Judge 预测池统一数据加载层
P9.2 新增：从 data/pool/ 读取 JSON，提供安全读取函数。
"""

from pathlib import Path
import json
import sys
from datetime import datetime, timezone

# 定位项目根目录（兼容 Vercel serverless 和本地运行）
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data" / "pool"
ACTIVE_ROUND_ID = "run-7"
ACTIVE_DATE = "2026-06-03"


def _now_iso():
    """返回当前 UTC ISO 时间戳"""
    return datetime.now(timezone.utc).isoformat()

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


def get_settlement_readiness(round_id: str = None):
    """
    P14.0：读取 provider-covered settlement readiness 红绿灯。
    """
    round_id = round_id or ACTIVE_ROUND_ID
    data = _read_json(f"reports/settlement_readiness_{round_id}.json", default=None)
    if data:
        return data
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
        "blockers": ["settlement_readiness_file_missing"],
    }


# ────────── P10.3 Settlements ───────────────────────────────────────────────

def get_settlements(round_id: str = None):
    """
    P10.3 实现：返回结算数据。
    - 无 round_id → 返回 data/pool/settlements/index.json
    - 有 round_id → 返回 data/pool/settlements/{round_id}.json
    - 文件不存在 → 返回 missing 结构，不崩溃
    """
    if round_id is None:
        data = _read_json("settlements/index.json", default=None)
        if data:
            return data
        return {"version": "p10.3", "updated_at": "", "rounds": []}

    fname = f"settlements/{round_id}.json"
    data = _read_json(fname, default=None)
    if data:
        return data
    return {
        "version": "p10.3",
        "round_id": round_id,
        "missing": True,
        "error": "settlement not found",
        "settlement_status": "missing",
        "valid_for_leaderboard_update": False,
        "settlements": [],
    }


def get_settlement(round_id: str = None):
    """
    P10.3 实现：获取单个 round 的完整结算结果。
    与 get_settlements(round_id) 相同，提供更具语义的别名。
    """
    if not round_id:
        return {"missing": True, "error": "round_id required"}
    return get_settlements(round_id=round_id)


# ────────── P11.0 Run Manifests & Ingested Outputs ──────────────────────────

def get_run_manifests():
    """
    P11.0 实现：返回所有 run manifest 索引。
    目录不存在或空 → 返回空结构。
    """
    manifests_dir = DATA_DIR / "run_manifests"
    rounds = []
    if manifests_dir.exists():
        for json_file in sorted(manifests_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                rounds.append({
                    "round_id": data.get("round_id", json_file.stem),
                    "date": data.get("date", ""),
                    "path": str(json_file.relative_to(ROOT_DIR)),
                    "seats_total": data.get("seats_total", 0),
                    "run_marker": data.get("run_marker", ""),
                })
            except Exception:
                continue
    return {"version": "p11.0", "updated_at": _now_iso(), "rounds": rounds}


def get_run_manifest(round_id: str = None):
    """
    P11.0 实现：获取单个 run manifest。
    - 文件不存在 → 返回 missing 结构
    """
    if not round_id:
        return {"missing": True, "error": "round_id required"}
    data = _read_json(f"run_manifests/{round_id}.json", default=None)
    if data:
        return data
    return {
        "version": "p11.0",
        "round_id": round_id,
        "missing": True,
        "error": "run manifest not found",
        "seats": [],
    }


def get_prompt_index(round_id: str = None):
    """
    P11.0 实现：返回某轮 prompt 目录下的文件索引。
    - round_id=None → 返回所有 round 的 prompt 索引
    """
    if round_id is None:
        prompts_base = DATA_DIR / "prompts"
        rounds = []
        if prompts_base.exists():
            for rd in sorted(prompts_base.iterdir()):
                if rd.is_dir():
                    md_files = sorted(rd.glob("*.md"))
                    rounds.append({
                        "round_id": rd.name,
                        "prompt_count": len(md_files),
                        "prompts": [p.name for p in md_files],
                    })
        return {"version": "p11.0", "rounds": rounds}

    prompts_dir = DATA_DIR / "prompts" / round_id
    if not prompts_dir.exists():
        return {"version": "p11.0", "round_id": round_id, "prompt_count": 0, "prompts": []}

    md_files = sorted(prompts_dir.glob("*.md"))
    return {
        "version": "p11.0",
        "round_id": round_id,
        "prompt_count": len(md_files),
        "prompts": [p.name for p in md_files],
    }


def get_ingested_outputs(round_id: str = None):
    """
    P11.0 实现：返回 ingest 后的标准化输出索引。
    - round_id=None → 返回所有 round 索引
    """
    if round_id is None:
        ingested_base = DATA_DIR / "model_outputs" / "ingested"
        rounds = []
        if ingested_base.exists():
            for rd in sorted(ingested_base.iterdir()):
                if rd.is_dir():
                    index_file = rd / "index.json"
                    if index_file.exists():
                        try:
                            data = json.loads(index_file.read_text(encoding="utf-8"))
                            rounds.append({
                                "round_id": rd.name,
                                "outputs_total": data.get("outputs_total", 0),
                                "outputs_found": data.get("outputs_found", 0),
                            })
                        except Exception:
                            rounds.append({"round_id": rd.name, "error": "parse failed"})
        return {"version": "p11.0", "rounds": rounds}

    try:
        data = json.loads((DATA_DIR / "model_outputs" / "ingested" / round_id / "index.json").read_text(encoding="utf-8"))
        return data
    except Exception:
        return {
            "version": "p11.0",
            "round_id": round_id,
            "missing": True,
            "error": "ingested outputs not found",
            "outputs": [],
        }


# ---------- P11.1 补跑机制 ----------

def get_rerun_attempts(round_id: str = None):
    """
    P11.1 新增：返回补跑 attempt ledger 索引。
    - round_id=None → 返回所有 rerun_attempts 摘要
    - round_id 指定 → 返回该 round 的 attempt ledger
    """
    if round_id is None:
        ra_dir = DATA_DIR / "rerun_attempts"
        rounds = []
        if ra_dir.exists():
            for json_file in sorted(ra_dir.glob("*.json")):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    s = data.get("summary", {})
                    rounds.append({
                        "round_id": data.get("round_id", json_file.stem),
                        "queue_total": s.get("queue_total", 0),
                        "planned_attempts": s.get("planned_attempts", 0),
                        "state": s.get("state", "unknown"),
                    })
                except Exception:
                    rounds.append({"round_id": json_file.stem, "error": "parse failed"})
        return {"version": "p11.1", "rounds": rounds}

    data = _read_json(f"rerun_attempts/{round_id}.json", default=None)
    if data:
        return data
    return {
        "version": "p11.1",
        "round_id": round_id,
        "missing": True,
        "error": "rerun attempt ledger not found",
        "summary": {"queue_total": 0, "planned_attempts": 0, "state": "missing"},
        "attempts": [],
    }


def get_rerun_attempt(round_id: str = None):
    """
    P11.1 新增：等价于 get_rerun_attempts(round_id)，提供别名。
    """
    return get_rerun_attempts(round_id=round_id)


def get_ingested_rerun_outputs(round_id: str = None, attempt_no: int = None):
    """
    P11.1 新增：返回补跑 ingest 后的标准化输出索引。
    - round_id=None → 返回所有 round 索引
    - round_id + attempt_no → 返回具体 attempt 的 index
    """
    if round_id is None:
        ingested_base = DATA_DIR / "model_outputs" / "ingested_rerun"
        rounds = []
        if ingested_base.exists():
            for rd in sorted(ingested_base.iterdir()):
                if rd.is_dir():
                    for att_dir in sorted(rd.iterdir()):
                        if att_dir.is_dir() and att_dir.name.startswith("attempt-"):
                            index_file = att_dir / "index.json"
                            if index_file.exists():
                                try:
                                    data = json.loads(index_file.read_text(encoding="utf-8"))
                                    rounds.append({
                                        "round_id": rd.name,
                                        "attempt_no": data.get("attempt_no", 0),
                                        "outputs_total": data.get("outputs_total", 0),
                                        "outputs_found": data.get("outputs_found", 0),
                                    })
                                except Exception:
                                    rounds.append({"round_id": rd.name, "attempt_no": att_dir.name, "error": "parse failed"})
        return {"version": "p11.1", "rounds": rounds}

    if attempt_no is None:
        # 返回该 round 下所有 attempt
        ingested_base = DATA_DIR / "model_outputs" / "ingested_rerun" / round_id
        attempts_list = []
        if ingested_base.exists():
            for att_dir in sorted(ingested_base.iterdir()):
                if att_dir.is_dir() and att_dir.name.startswith("attempt-"):
                    index_file = att_dir / "index.json"
                    if index_file.exists():
                        try:
                            data = json.loads(index_file.read_text(encoding="utf-8"))
                            attempts_list.append({
                                "attempt_no": data.get("attempt_no", 0),
                                "outputs_total": data.get("outputs_total", 0),
                                "outputs_found": data.get("outputs_found", 0),
                            })
                        except Exception:
                            attempts_list.append({"attempt_no": att_dir.name, "error": "parse failed"})
        return {"version": "p11.1", "round_id": round_id, "attempts": attempts_list}

    # round_id + attempt_no
    try:
        index_path = DATA_DIR / "model_outputs" / "ingested_rerun" / round_id / f"attempt-{attempt_no}" / "index.json"
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {
            "version": "p11.1",
            "round_id": round_id,
            "attempt_no": attempt_no,
            "missing": True,
            "error": "ingested rerun outputs not found",
            "outputs_total": 0,
            "outputs_found": 0,
            "outputs_missing": 0,
            "outputs": [],
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


# ────────── P12.0 Pipeline Runs ──────────────────────────────────────────────

def get_pipeline_runs():
    """
    P12.0 新增：返回 data/pool/pipeline_runs/*.json 摘要列表。
    目录不存在或空 → 返回空结构。
    """
    pr_dir = DATA_DIR / "pipeline_runs"
    if not pr_dir.exists():
        return {"version": "p12.0", "updated_at": _now_iso(), "pipeline_runs": []}

    runs = []
    for f in sorted(pr_dir.glob("*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            runs.append({
                "date":          d.get("date", ""),
                "round_id":      d.get("round_id", ""),
                "generated_at":  d.get("generated_at", ""),
                "final_status":  d.get("final_status", ""),
                "summary":       d.get("summary", {}),
                "blockers_count": len(d.get("blockers", [])),
                "warnings_count": len(d.get("warnings", [])),
                "file":          f.name,
            })
        except Exception:
            runs.append({"date": "", "round_id": f.stem, "file": f.name, "error": "parse_failed"})
    return {"version": "p12.0", "updated_at": _now_iso(), "pipeline_runs": runs}


def get_pipeline_run(date=None, round_id=None):
    """
    P12.0 新增：返回单个 pipeline run 完整数据。
    - 传 date + round_id → 读取 data/pool/pipeline_runs/{date}_{round_id}.json
    - 文件不存在 → 返回 missing 结构，不崩溃
    """
    if not date or not round_id:
        return {
            "version":      "p12.0",
            "missing":      True,
            "error":        "date and round_id required",
            "pipeline_run": None,
        }

    filename = f"{date}_{round_id}.json"
    data = _read_json(f"pipeline_runs/{filename}", default=None)
    if data:
        return {
            "version":      "p12.0",
            "missing":      False,
            "pipeline_run": data,
        }

    return {
        "version":      "p12.0",
        "date":         date,
        "round_id":     round_id,
        "missing":      True,
        "error":        "pipeline run not found",
        "pipeline_run": None,
    }


def get_latest_pipeline_run():
    """
    P12.1 新增：返回最新的 pipeline run 摘要。
    按 generated_at 或 filename 排序，最新的在前。
    找不到时返回 missing 结构。
    """
    runs = get_pipeline_runs()
    pr_list = runs.get("pipeline_runs", [])
    if not pr_list:
        return {
            "version": "p12.1",
            "missing": True,
            "error": "no pipeline runs found",
            "latest": None,
        }
    # runs are already sorted reverse by filename; take the first valid one
    for r in pr_list:
        if r.get("date") and r.get("final_status"):
            return {
                "version": "p12.1",
                "missing": False,
                "latest": r,
            }
    return {
        "version": "p12.1",
        "missing": True,
        "error": "no valid pipeline run",
        "latest": None,
    }


def get_latest_daily_report():
    """
    P12.1 新增：返回最新的 daily report 摘要。
    扫描 data/pool/daily_reports/*.json，按 filename 排序。
    找不到时返回 missing 结构。
    """
    dr_dir = DATA_DIR / "daily_reports"
    if not dr_dir.exists():
        return {
            "version": "p12.1",
            "missing": True,
            "error": "daily_reports dir not found",
            "latest": None,
        }

    json_files = sorted(dr_dir.glob("*.json"), reverse=True)
    for f in json_files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            return {
                "version": "p12.1",
                "missing": False,
                "latest": {
                    "file": f.name,
                    "date": d.get("date", ""),
                    "round_id": d.get("round_id", ""),
                    "generated_at": d.get("generated_at", ""),
                    "summary": d.get("summary", {}),
                },
            }
        except Exception:
            continue

    return {
        "version": "p12.1",
        "missing": True,
        "error": "no valid daily reports found",
        "latest": None,
    }


# ───────── P12.2 Ops Readiness ─────────────────────────────────────────────

def get_ops_readiness():
    """
    P12.2 新增：读取 data/pool/ops_readiness/latest.json。
    文件不存在时返回 missing 结构，不崩溃。
    """
    data = _read_json("ops_readiness/latest.json", default=None)
    if data:
        return data
    return {
        "version":         "p12.2",
        "generated_at":     "",
        "overall_status":   "missing",
        "missing":          True,
        "error":            "ops_readiness/latest.json not found — run ops/check_ops_readiness.py",
        "checks":           [],
        "warnings":         [],
        "blockers":         [],
        "next_actions":     [],
    }


# ───────── P13.0 Provider & Odds ───────────────────────────────────────────

def get_provider_status():
    """
    P13.0 新增：读取 data/pool/provider_status/latest.json。
    文件不存在时返回 missing 结构，不崩溃。
    """
    data = _read_json("provider_status/latest.json", default=None)
    if data:
        return data
    return {
        "version":       "p13.0",
        "generated_at":   "",
        "overall":        "missing",
        "missing":        True,
        "error":          "provider_status/latest.json not found — run ops/check_provider_config.py",
        "providers":      [],
        "blockers":       [],
        "warnings":       [],
    }


def get_odds_snapshots(date=None, snapshot_label=None, provider=None):
    """
    P10.1/P13.0：返回赔率快照摘要列表。
    - 无参数：返回 index.json 中所有快照摘要
    - 传 provider：优先读 provider-specific 文件
    - 向后兼容：无 provider 时读旧的 {date}_{label}.json
    """
    # 如果指定了 provider，尝试读 provider-specific 文件
    if date and snapshot_label and provider:
        specific_path = DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}_{provider}.json"
        if specific_path.exists():
            try:
                d = json.loads(specific_path.read_text(encoding="utf-8"))
                summary = d.get("summary", {})
                return {
                    "version":          "p13.0",
                    "provider_match":    True,
                    "snapshots": [{
                        "date":                  date,
                        "snapshot_label":        snapshot_label,
                        "provider":              provider,
                        "path":                  f"data/pool/odds_snapshots/{date}_{snapshot_label}_{provider}.json",
                        "valid_odds_rows":       summary.get("valid_odds_rows", 0),
                        "coverage_status":        _odds_coverage_status(summary),
                        "missing_market_coverage": summary.get("missing_market_coverage", 0),
                        "provider_unavailable":   summary.get("provider_unavailable", False),
                    }],
                }
            except Exception:
                pass  # fall through to index

    # 向后兼容：读 index.json
    index_path = DATA_DIR / "odds_snapshots" / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            snapshots = index.get("snapshots", [])
            # 过滤条件
            if date:
                snapshots = [s for s in snapshots if s.get("date") == date]
            if snapshot_label:
                snapshots = [s for s in snapshots if s.get("snapshot_label") == snapshot_label]
            if provider:
                snapshots = [s for s in snapshots if s.get("provider") == provider]
            return {
                "version":       "p13.0",
                "provider_match": False,
                "snapshots":     snapshots,
            }
        except Exception:
            pass

    return {
        "version":   "p13.0",
        "missing":    True,
        "snapshots": [],
        "error":      "no odds snapshots found",
    }


def get_odds_snapshot(date=None, snapshot_label=None, provider=None):
    """
    P13.0 新增：返回单个赔率快照完整数据。
    优先级：
      1. provider-specific 文件
      2. index.json 中匹配的记录
      3. 旧版 {date}_{label}.json（向后兼容）
    """
    # 1. provider-specific
    if date and snapshot_label and provider:
        specific_path = DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}_{provider}.json"
        if specific_path.exists():
            try:
                return {
                    "version": "p13.0",
                    "source":  "provider_specific",
                    "data":   json.loads(specific_path.read_text(encoding="utf-8")),
                }
            except Exception:
                pass

    # 2. 旧版文件（向后兼容 manual_stub）
    if date and snapshot_label:
        old_path = DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}.json"
        if old_path.exists():
            try:
                return {
                    "version": "p13.0",
                    "source":  "legacy_file",
                    "data":   json.loads(old_path.read_text(encoding="utf-8")),
                }
            except Exception:
                pass

    return {
        "version": "p13.0",
        "missing": True,
        "error":   f"odds snapshot not found for date={date}, label={snapshot_label}, provider={provider}",
        "data":   None,
    }


def _odds_coverage_status(summary: dict) -> str:
    """根据 summary 判断 coverage_status。"""
    provider_unavail = summary.get("provider_unavailable", False)
    valid = summary.get("valid_odds_rows", 0)
    total = summary.get("odds_rows", 0)

    if provider_unavail:
        return "provider_not_configured"
    if total > 0 and valid == 0:
        return "provider_responded_but_no_match_coverage"
    if valid > 0:
        return "provider_covered_internal_matches"
    return "unknown"


def get_provider_smoke(round_id: str = None, date: str = None):
    """
    P13.0 新增：读取 provider smoke test 结果。
    优先读取 data/pool/provider_smoke/{round_id}_{date}.json，
    如果不存在，返回结构化默认值（不崩溃）。
    """
    if round_id and date:
        smoke_path = DATA_DIR / "provider_smoke" / f"{round_id}_{date}.json"
        if smoke_path.exists():
            try:
                data = json.loads(smoke_path.read_text(encoding="utf-8"))
                return data
            except Exception as e:
                print(f"[pool_data] WARNING: failed to read {smoke_path}: {e}", file=sys.stderr)

    # 返回结构化默认值
    return {
        "version":     "p13.0",
        "round_id":    round_id or "",
        "date":        date or "",
        "status":      "BLOCKED_PROVIDER_NOT_CONFIGURED",
        "summary": {
            "provider":           "the_odds_api",
            "configured":         False,
            "provider_responded": None,
            "matched_internal_matches": 0,
            "valid_odds_rows":   0,
            "coverage_status":   "real_odds_provider_not_configured",
        },
        "blocks":    [],
        "warnings":  ["THE_ODDS_API_KEY is not set"],
        "generated_at": _now_iso(),
    }


def get_output_dropbox_report(round_id: str = None):
    """
    P13.0 新增：读取模型输出投喂目录状态。
    读取 data/pool/model_outputs/raw/{round_id}/dropbox_check.json。
    """
    if not round_id:
        round_id = ACTIVE_ROUND_ID

    dropbox_path = DATA_DIR / "model_outputs" / "raw" / round_id / "dropbox_check.json"
    if dropbox_path.exists():
        try:
            data = json.loads(dropbox_path.read_text(encoding="utf-8"))
            return data
        except Exception as e:
            print(f"[pool_data] WARNING: failed to read {dropbox_path}: {e}", file=sys.stderr)

    # 返回默认值
    return {
        "version":          "p13.0",
        "round_id":         round_id,
        "status":           "waiting_for_manual_ingest",
        "outputs_expected":  12,
        "outputs_found":    0,
        "outputs_missing":  12,
        "missing_models":   [],
        "empty_files":     [],
        "invalid_names":   [],
        "has_run_marker":  False,
        "has_round_id":    False,
        "details":          {},
        "generated_at":    _now_iso(),
    }


# ───────── P14.0 Runtime Summary ───────────────────────────────────────────

def get_runtime_summary(round_id: str = None, date: str = None):
    """
    P14.0：返回预测池当前运行态 + 历史归档摘要。
    这个接口专门给新版五页 UI 使用，避免首页只读 run-5 或隐藏旧档案后
    让欧冠前哨、历史投注和最新真实回收状态看起来“消失”。
    """
    round_id = round_id or ACTIVE_ROUND_ID
    date = date or ACTIVE_DATE

    models = get_model_accounts()
    leaderboard = get_leaderboard()
    archives = get_frontend_archives() or {}
    provider = get_provider_status()
    provider_smoke = get_provider_smoke(round_id=round_id, date=date)
    dropbox = get_output_dropbox_report(round_id=round_id)
    ingested = get_ingested_outputs(round_id=round_id)
    model_runs = get_model_runs(round_id=round_id)
    receipts = get_bet_receipts(round_id=round_id)
    readiness = get_settlement_readiness(round_id=round_id)
    settlements = get_settlement(round_id=round_id)
    daily_report = get_daily_report(date=date, round_id=round_id) or {}
    pipeline = get_pipeline_run(date=date, round_id=round_id)
    pipeline_run = pipeline.get("pipeline_run") if isinstance(pipeline, dict) else None

    model_list = models.get("models", []) if isinstance(models, dict) else []
    leaderboard_rows = []
    if isinstance(leaderboard, dict):
        leaderboard_rows = leaderboard.get("leaderboard") or leaderboard.get("models") or []

    ingested_outputs = []
    if isinstance(ingested, dict):
        ingested_outputs = ingested.get("outputs") or []

    receipts_summary = receipts.get("summary", {}) if isinstance(receipts, dict) else {}
    accepted_receipts = []
    if isinstance(receipts, dict):
        accepted_receipts = receipts.get("accepted_receipts") or receipts.get("receipts") or []

    smoke_summary = provider_smoke.get("summary", {}) if isinstance(provider_smoke, dict) else {}
    model_run_summary = model_runs.get("summary", {}) if isinstance(model_runs, dict) else {}
    settlement_summary = settlements.get("summary", {}) if isinstance(settlements, dict) else {}
    pipeline_summary = {}
    if isinstance(pipeline_run, dict):
        pipeline_summary = pipeline_run.get("summary", {})

    round_results = archives.get("round_results", []) if isinstance(archives, dict) else []
    ucl_bets = archives.get("ucl_bets", []) if isinstance(archives, dict) else []
    run4_archive = archives.get("run4_model_archive", []) if isinstance(archives, dict) else []
    run5_archive = archives.get("run5_model_archive", []) if isinstance(archives, dict) else []

    zero_stake_receipts = 0
    for receipt in accepted_receipts:
        try:
            if float(receipt.get("total_stake") or 0) == 0:
                zero_stake_receipts += 1
        except Exception:
            pass

    accepted_bets = receipts_summary.get("accepted_bets")
    if accepted_bets is None:
        accepted_bets = receipts_summary.get("candidate_bets", 0)

    has_betting_gap = bool(
        (readiness.get("provider_covered_accepted_bets", 0) or 0) == 0
        and (dropbox.get("outputs_found") or len(ingested_outputs) or 0) > 0
    )

    data_gaps = daily_report.get("data_gaps", []) if isinstance(daily_report, dict) else []
    next_actions = daily_report.get("next_actions", []) if isinstance(daily_report, dict) else []
    pipeline_next_actions = pipeline_run.get("next_actions", []) if isinstance(pipeline_run, dict) else []
    pipeline_blockers = pipeline_run.get("blockers", []) if isinstance(pipeline_run, dict) else []
    if has_betting_gap:
        next_actions = list(next_actions) + [{
            "action": "regenerate_bet_receipts_with_real_odds",
            "stage": "P14.0",
            "blocking": True,
            "reason": f"{round_id} has real model outputs and valid provider odds, but current receipts contain 0 accepted bets",
        }]
    for action in pipeline_next_actions:
        if isinstance(action, dict):
            next_actions.append(action)
        else:
            next_actions.append({
                "action": "pipeline_next_action",
                "stage": "P12.0",
                "blocking": pipeline_run.get("final_status") == "blocked" if isinstance(pipeline_run, dict) else False,
                "reason": str(action),
            })

    return {
        "version": "p14.0",
        "generated_at": _now_iso(),
        "current_round": round_id,
        "date": date,
        "active_models_count": len(model_list),
        "active_models": [
            {
                "model_account": m.get("model_account"),
                "display_name": m.get("display_name"),
                "status": m.get("status"),
            }
            for m in model_list
        ],
        "current_ranking": leaderboard_rows[:12],
        "provider": {
            "overall": provider.get("overall") if isinstance(provider, dict) else "unknown",
            "status": provider_smoke.get("status") if isinstance(provider_smoke, dict) else "unknown",
            "configured": smoke_summary.get("configured", False),
            "provider_responded": smoke_summary.get("provider_responded"),
            "valid_odds_rows": smoke_summary.get("valid_odds_rows", 0),
            "odds_rows": smoke_summary.get("odds_rows", 0),
            "coverage_status": smoke_summary.get("coverage_status", "unknown"),
        },
        "model_outputs": {
            "status": dropbox.get("status"),
            "outputs_expected": dropbox.get("outputs_expected") or len(model_list),
            "outputs_found": dropbox.get("outputs_found") or len(ingested_outputs),
            "outputs_missing": dropbox.get("outputs_missing", 0),
            "missing_models": dropbox.get("missing_models") or dropbox.get("missing_files") or [],
            "ingested_models": [o.get("model_account") for o in ingested_outputs if o.get("model_account")],
        },
        "model_runs": {
            "summary": model_run_summary,
            "valid_receipt": model_run_summary.get("valid_receipt", 0),
            "needs_rerun": model_run_summary.get("needs_rerun", 0),
        },
        "betting": {
            "summary": receipts_summary,
            "accepted_receipts": len(accepted_receipts),
            "zero_stake_receipts": zero_stake_receipts,
            "accepted_bets": accepted_bets or 0,
            "provider_covered_accepted_bets": readiness.get("provider_covered_accepted_bets", 0),
            "fallback_bets": readiness.get("fallback_bets", receipts_summary.get("fallback_bets", 0)),
            "analysis_only_bets": readiness.get("analysis_only_bets", receipts_summary.get("analysis_only_bets", 0)),
            "eligible_board_rows": readiness.get("eligible_board_rows", receipts_summary.get("eligible_board_rows", 0)),
            "valid_for_settlement": readiness.get("valid_for_settlement", False),
            "gap": has_betting_gap,
        },
        "settlement_readiness": readiness,
        "settlement": {
            "status": settlements.get("settlement_status") if isinstance(settlements, dict) else "unknown",
            "summary": settlement_summary,
        },
        "automation": {
            "pipeline_status": pipeline_run.get("final_status") if isinstance(pipeline_run, dict) else "unknown",
            "steps_passed": pipeline_summary.get("steps_passed", 0),
            "steps_total": pipeline_summary.get("steps_total", 0),
            "deploy_step": "skipped" if isinstance(pipeline_run, dict) else "unknown",
            "data_gaps": data_gaps,
            "pipeline_blockers": pipeline_blockers,
            "pipeline_next_actions": pipeline_next_actions,
            "next_actions": next_actions,
        },
        "archives": {
            "updated_at": archives.get("updated_at") if isinstance(archives, dict) else "",
            "counts": {
                "round_results": len(round_results),
                "ucl_bets": len(ucl_bets),
                "run4_model_archive": len(run4_archive),
                "run5_model_archive": len(run5_archive),
            },
            "round_results": round_results,
            "ucl_bets": ucl_bets,
            "run4_model_archive": run4_archive,
            "run5_model_archive": run5_archive,
        },
    }
