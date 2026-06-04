#!/usr/bin/env python3
"""
ops/run_daily_pool_pipeline.py
P12.0 一键流水线 — 串联 P10.0–P11.1 全部子脚本

用法:
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --dry-run
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --skip-browser
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --continue-on-warning
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --deploy

职责:
  1. 串联已有 P10.0–P11.1 脚本
  2. 支持 dry-run（不写文件）
  3. 每一步写入状态
  4. 不因为"等待人工模型输出"而失败
  5. 不编造模型输出、赔率、投注、结算
  6. 清楚标记 blockers / warnings / skipped
  7. 让前端系统健康页可以展示 pipeline 状态
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
OPS_DIR = ROOT_DIR / "ops"
DATA_DIR = ROOT_DIR / "data" / "pool"
PIPELINE_DIR = DATA_DIR / "pipeline_runs"

# ── 子脚本引用 ───────────────────────────────────────────────────────────────
SCRIPTS = {
    "sync_matches":           OPS_DIR / "sync_matches.py",
    "sync_results":           OPS_DIR / "sync_results.py",
    "sync_odds_snapshots":    OPS_DIR / "sync_odds_snapshots.py",
    "generate_eligible_board": OPS_DIR / "generate_eligible_board.py",
    "ai_judge_daily_pool":    OPS_DIR / "ai_judge_daily_pool.py",
    "classify_model_output":  OPS_DIR / "classify_model_output.py",
    "validate_model_outputs": OPS_DIR / "validate_model_outputs.py",
    "settle_pool_round":      OPS_DIR / "settle_pool_round.py",
    "rerun_failed_seats":     OPS_DIR / "rerun_failed_seats.py",
    "generate_daily_report":  OPS_DIR / "generate_daily_pool_report.py",
    "check_data_health":      OPS_DIR / "check_pool_data_health.py",
}

# ── 步骤定义 ──────────────────────────────────────────────────────────────────
STEPS_ORDER = [
    "preflight",
    "sync_matches",
    "sync_results",
    "sync_odds_snapshots",
    "generate_eligible_board",
    "generate_prompts",
    "ingest",
    "classify_model_output",
    "validate_model_outputs",
    "settle_pool_round",
    "rerun_failed_seats",
    "generate_daily_report",
    "check_data_health",
    "post_run_guardrails",
    "deploy",
]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _run_cmd(cmd_parts, cwd=None, dry_run=False, timeout=120):
    """执行子命令，返回 (returncode, stdout, stderr, duration_ms)。"""
    if dry_run:
        return 0, "[DRY-RUN] would execute: " + " ".join(str(p) for p in cmd_parts), "", 0

    t0 = time.time()
    try:
        r = subprocess.run(
            [str(p) for p in cmd_parts],
            cwd=cwd or ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        dur = int((time.time() - t0) * 1000)
        return r.returncode, r.stdout or "", r.stderr or "", dur
    except subprocess.TimeoutExpired:
        dur = int((time.time() - t0) * 1000)
        return -1, "", f"TIMEOUT after {timeout}s", dur
    except Exception as e:
        dur = int((time.time() - t0) * 1000)
        return -1, "", str(e), dur


def _tail(s, n=500):
    """取字符串尾部最多 n 字符。"""
    if not s:
        return ""
    return s[-n:] if len(s) > n else s


def _resolve_odds_provider(provider):
    if provider == "auto":
        return "the_odds_api" if os.environ.get("THE_ODDS_API_KEY") else "manual_stub"
    return provider


def _odds_snapshot_path(date, snapshot_label, provider):
    if provider and provider != "manual_stub":
        return DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}_{provider}.json"
    return DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}.json"


def _load_json(path, default=None):
    if not Path(path).exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ── 步骤执行函数 ──────────────────────────────────────────────────────────────

def step_preflight(args, run_state):
    """检查所有子脚本存在性。"""
    t0 = time.time()
    missing = []
    for name, path in SCRIPTS.items():
        if not path.exists():
            missing.append(name)

    dur = int((time.time() - t0) * 1000)
    if missing:
        return {
            "step": "preflight",
            "status": "blocked",
            "command": f"check scripts: {', '.join(missing)} not found",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": dur,
            "stdout_tail": "",
            "stderr_tail": "",
            "outputs": [],
            "warnings": [f"Missing scripts: {', '.join(missing)}"],
            "reason": f"hard blocker: {len(missing)} scripts missing",
        }
    return {
        "step": "preflight",
        "status": "pass",
        "command": "all scripts present",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": "",
        "stderr_tail": "",
        "outputs": [str(path) for path in SCRIPTS.values()],
    }


def step_sync_matches(args, run_state):
    cmd = ["python3", str(SCRIPTS["sync_matches"]), "--date", args.date, "--days", "14"]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=120)

    output_file = f"data/pool/matches/snapshots/{args.date}.json"
    exists = (DATA_DIR / "matches" / "snapshots" / f"{args.date}.json").exists() if not args.dry_run else True

    status = "pass" if rc == 0 and exists else "failed"

    return {
        "step": "sync_matches",
        "status": status,
        "command": "python3 ops/sync_matches.py --date " + args.date + " --days 14",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [output_file] if status == "pass" else [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"] + ([err] if err else []),
        "reason": "" if status == "pass" else f"failed: rc={rc}" + (f", stderr: {_tail(err, 100)}" if err else ""),
    }


def step_sync_results(args, run_state):
    cmd = ["python3", str(SCRIPTS["sync_results"]), "--date", args.date]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    output_file = f"data/pool/match_results/{args.date}.json"
    exists = (DATA_DIR / "match_results" / f"{args.date}.json").exists() if not args.dry_run else True

    status = "pass" if rc == 0 and exists else "failed"

    return {
        "step": "sync_results",
        "status": status,
        "command": "python3 ops/sync_results.py --date " + args.date,
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [output_file] if status == "pass" else [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"] + ([err] if err else []),
        "reason": "" if status == "pass" else f"failed: rc={rc}",
    }


def step_sync_odds_snapshots(args, run_state):
    provider = _resolve_odds_provider(args.odds_provider)
    run_state["odds_provider"] = provider
    output_path = _odds_snapshot_path(args.date, "T-1h", provider)
    output_file = str(output_path.relative_to(ROOT_DIR))
    if args.reuse_existing_odds:
        exists = output_path.exists() if not args.dry_run else True
        snapshot = _load_json(output_path, default={}) if exists and not args.dry_run else {}
        summary = snapshot.get("summary", {}) if isinstance(snapshot, dict) else {}
        run_state["valid_odds_rows"] = summary.get("valid_odds_rows", 0)
        status = "pass" if exists else "failed"
        return {
            "step": "sync_odds_snapshots",
            "status": status,
            "command": f"reuse existing {output_file}",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 0,
            "stdout_tail": f"reused={exists}\nprovider={provider}\nvalid_odds_rows={run_state.get('valid_odds_rows', 0)}",
            "stderr_tail": "",
            "outputs": [output_file] if status == "pass" else [],
            "warnings": [] if status == "pass" else [f"missing_existing_odds_snapshot={output_file}"],
            "reason": "" if status == "pass" else "existing odds snapshot missing",
        }

    cmd = [
        "python3", str(SCRIPTS["sync_odds_snapshots"]),
        "--date", args.date,
        "--snapshot-label", "T-1h",
        "--provider", provider,
    ]
    if provider != "manual_stub":
        cmd.append("--save-raw")
    if args.strict_real_provider and provider != "manual_stub":
        cmd.append("--strict-real-provider")
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    exists = output_path.exists() if not args.dry_run else True
    snapshot = _load_json(output_path, default={}) if exists and not args.dry_run else {}
    summary = snapshot.get("summary", {}) if isinstance(snapshot, dict) else {}
    run_state["valid_odds_rows"] = summary.get("valid_odds_rows", 0)

    status = "pass" if rc == 0 and exists else "failed"
    warnings_list = [] if rc == 0 else [f"returncode={rc}"] + ([err] if err else [])
    if status == "pass" and provider == "manual_stub":
        warnings_list.append("odds_provider_manual_stub: no real odds provider used for prompt generation")

    return {
        "step": "sync_odds_snapshots",
        "status": status,
        "command": f"python3 ops/sync_odds_snapshots.py --date {args.date} --snapshot-label T-1h --provider {provider}",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [output_file] if status == "pass" else [],
        "warnings": warnings_list,
        "reason": "" if status == "pass" else f"failed: rc={rc}",
    }


def step_generate_eligible_board(args, run_state):
    provider = _resolve_odds_provider(args.odds_provider)
    cmd = [
        "python3", str(SCRIPTS["generate_eligible_board"]),
        "--date", args.date,
        "--round", args.round_id,
        "--snapshot-label", "T-1h",
        "--provider", provider,
    ]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)
    output_file = f"data/pool/odds/eligible_board/{args.round_id}.json"
    board_path = DATA_DIR / "odds" / "eligible_board" / f"{args.round_id}.json"
    board = _load_json(board_path, default={}) if board_path.exists() and not args.dry_run else {}
    rows = int((board.get("summary", {}) if isinstance(board, dict) else {}).get("eligible_board_rows") or 0)
    run_state["eligible_board_rows"] = rows

    status = "pass" if rc == 0 and (rows > 0 or args.dry_run) else "failed"
    warnings_list = [] if rc == 0 else [f"returncode={rc}"]
    if rc == 0 and rows == 0:
        warnings_list.append("eligible_board_empty")

    return {
        "step": "generate_eligible_board",
        "status": status,
        "command": f"python3 ops/generate_eligible_board.py --date {args.date} --round {args.round_id} --snapshot-label T-1h --provider {provider}",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [output_file] if status == "pass" else [],
        "warnings": warnings_list + ([err] if err and status == "failed" else []),
        "reason": "" if status == "pass" else "eligible board generation failed or produced 0 rows",
    }


def step_generate_prompts(args, run_state):
    cmd = [
        "python3", str(SCRIPTS["ai_judge_daily_pool"]), "run",
        "--date", args.date,
        "--round", args.round_id,
        "--odds-provider", _resolve_odds_provider(args.odds_provider),
        "--generate-prompts-only",
    ]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    prompt_count = 0
    if not args.dry_run:
        prompts_dir = DATA_DIR / "prompts" / args.round_id
        if prompts_dir.exists():
            prompt_count = len(list(prompts_dir.glob("*.md")))

    status = "pass" if rc == 0 else "failed"

    return {
        "step": "generate_prompts",
        "status": status,
        "command": f"python3 ops/ai_judge_daily_pool.py run --date {args.date} --round {args.round_id} --odds-provider {_resolve_odds_provider(args.odds_provider)} --generate-prompts-only",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [f"data/pool/prompts/{args.round_id}/ ({prompt_count} prompts)"] if status == "pass" else [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"] + ([err] if err else []),
        "reason": "" if status == "pass" else f"failed: rc={rc}",
    }


def step_ingest(args, run_state):
    input_dir = f"data/pool/model_outputs/raw/{args.round_id}"
    cmd = [
        "python3", str(SCRIPTS["ai_judge_daily_pool"]), "ingest",
        "--round", args.round_id,
        "--input-dir", input_dir,
    ]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    # Check if outputs_found > 0
    outputs_found = 0
    if not args.dry_run:
        ingested_path = DATA_DIR / "model_outputs" / "ingested" / args.round_id / "index.json"
        if ingested_path.exists():
            try:
                ig = json.loads(ingested_path.read_text(encoding="utf-8"))
                outputs_found = ig.get("outputs_found", 0)
            except Exception:
                pass

    if rc != 0:
        status = "failed"
        warnings_list = [f"returncode={rc}"]
    elif outputs_found == 0:
        status = "skipped"
        warnings_list = ["waiting_for_manual_ingest: no raw model outputs found"]
        # Update run_state so downstream knows
        run_state["ingest_outputs_found"] = 0
    else:
        status = "pass"
        warnings_list = []

    reason = ""
    if outputs_found == 0 and status != "failed":
        reason = "waiting_for_manual_ingest: all 12 outputs missing, run-6 not failed — waiting for human to place model outputs"

    run_state["ingest_outputs_found"] = outputs_found

    return {
        "step": "ingest",
        "status": status,
        "command": f"python3 ops/ai_judge_daily_pool.py ingest --round {args.round_id} --input-dir {input_dir}",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [],
        "warnings": warnings_list + ([err] if err and status == "failed" else []),
        "reason": reason,
    }


def step_classify_model_output(args, run_state):
    outputs_found = run_state.get("ingest_outputs_found", 0)
    if outputs_found <= 0:
        return {
            "step": "classify_model_output",
            "status": "skipped",
            "command": "python3 ops/classify_model_output.py --round " + args.round_id,
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "outputs": [],
            "warnings": [],
            "reason": "skipped_waiting_for_model_outputs: no ingested outputs to classify",
        }

    cmd = ["python3", str(SCRIPTS["classify_model_output"]), "--round", args.round_id]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    status = "pass" if rc == 0 else "failed"

    return {
        "step": "classify_model_output",
        "status": status,
        "command": "python3 ops/classify_model_output.py --round " + args.round_id,
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [f"data/pool/model_runs/{args.round_id}.json"] if status == "pass" else [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"],
        "reason": "" if status == "pass" else f"failed: rc={rc}",
    }


def step_validate_model_outputs(args, run_state):
    model_runs_path = DATA_DIR / "model_runs" / f"{args.round_id}.json"
    if not model_runs_path.exists() and not args.dry_run:
        return {
            "step": "validate_model_outputs",
            "status": "skipped",
            "command": f"python3 ops/validate_model_outputs.py --round {args.round_id} --date {args.date}",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "outputs": [],
            "warnings": [],
            "reason": f"skipped_no_classified_outputs: model_runs/{args.round_id}.json not found",
        }

    # Also check if model_runs has actual outputs
    has_outputs = False
    if not args.dry_run and model_runs_path.exists():
        try:
            mr = json.loads(model_runs_path.read_text(encoding="utf-8"))
            runs = mr.get("runs", [])
            has_outputs = any(r.get("status") in ("valid_receipt", "needs_rerun_placeholder", "needs_rerun_context_polluted", "quota_blocked", "audit_only_refusal", "risk_refusal") for r in runs)
        except Exception:
            pass

    if args.dry_run:
        has_outputs = True  # assume has outputs for dry-run prediction

    if not has_outputs:
        return {
            "step": "validate_model_outputs",
            "status": "skipped",
            "command": f"python3 ops/validate_model_outputs.py --round {args.round_id} --date {args.date}",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "outputs": [],
            "warnings": [],
            "reason": "skipped_no_classified_outputs: no model outputs to validate",
        }

    cmd = [
        "python3", str(SCRIPTS["validate_model_outputs"]),
        "--round", args.round_id,
        "--date", args.date,
    ]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    status = "pass" if rc == 0 else "failed"

    return {
        "step": "validate_model_outputs",
        "status": status,
        "command": f"python3 ops/validate_model_outputs.py --round {args.round_id} --date {args.date}",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"],
        "reason": "" if status == "pass" else f"failed: rc={rc}",
    }


def step_settle_pool_round(args, run_state):
    bet_receipts_path = DATA_DIR / "bet_receipts" / f"{args.round_id}.json"
    if not bet_receipts_path.exists() and not args.dry_run:
        return {
            "step": "settle_pool_round",
            "status": "skipped",
            "command": f"python3 ops/settle_pool_round.py --round {args.round_id} --date {args.date}",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "outputs": [],
            "warnings": [],
            "reason": f"skipped_no_bet_receipts: bet_receipts/{args.round_id}.json not found",
        }

    cmd = [
        "python3", str(SCRIPTS["settle_pool_round"]),
        "--round", args.round_id,
        "--date", args.date,
    ]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    status = "pass" if rc == 0 else "failed"

    return {
        "step": "settle_pool_round",
        "status": status,
        "command": f"python3 ops/settle_pool_round.py --round {args.round_id} --date {args.date}",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [f"data/pool/settlements/{args.round_id}.json"] if status == "pass" else [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"],
        "reason": "" if status == "pass" else f"failed: rc={rc}",
    }


def step_rerun_failed_seats(args, run_state):
    rerun_queue_path = DATA_DIR / "rerun_queue" / f"{args.round_id}.json"
    if not rerun_queue_path.exists() and not args.dry_run:
        return {
            "step": "rerun_failed_seats",
            "status": "skipped",
            "command": f"python3 ops/rerun_failed_seats.py --round {args.round_id}",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "outputs": [],
            "warnings": [],
            "reason": f"skipped_no_rerun_queue: rerun_queue/{args.round_id}.json not found",
        }

    # For rerun, we only run if queue exists; use generate-prompts-only (not actual browser rerun)
    cmd = [
        "python3", str(SCRIPTS["rerun_failed_seats"]),
        "--round", args.round_id,
        "--generate-prompts-only",
        "--skip-browser",
    ]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    status = "pass" if rc == 0 else "failed"

    return {
        "step": "rerun_failed_seats",
        "status": status,
        "command": f"python3 ops/rerun_failed_seats.py --round {args.round_id} --generate-prompts-only --skip-browser",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [f"data/pool/rerun_attempts/{args.round_id}.json"] if status == "pass" else [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"],
        "reason": "" if status == "pass" else f"failed: rc={rc}",
    }


def step_generate_daily_report(args, run_state):
    """无论前面跳过多少，都应尽量执行。"""
    cmd = [
        "python3", str(SCRIPTS["generate_daily_report"]),
        "--date", args.date,
        "--round", args.round_id,
    ]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=60)

    json_out = f"data/pool/daily_reports/{args.date}_{args.round_id}.json"
    md_out = f"data/pool/daily_reports/{args.date}_{args.round_id}.md"

    json_exists = (DATA_DIR / "daily_reports" / f"{args.date}_{args.round_id}.json").exists() if not args.dry_run else True

    status = "pass" if rc == 0 and json_exists else ("failed" if rc != 0 else "pass_with_warnings")

    return {
        "step": "generate_daily_report",
        "status": status,
        "command": f"python3 ops/generate_daily_pool_report.py --date {args.date} --round {args.round_id}",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [json_out, md_out] if status in ("pass", "pass_with_warnings") else [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"],
        "reason": "" if status == "pass" else f"rc={rc}" if rc != 0 else "generated with warnings",
    }


def step_check_data_health(args, run_state):
    cmd = ["python3", str(SCRIPTS["check_data_health"])]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=30)

    status = "pass" if rc == 0 else "failed"

    return {
        "step": "check_data_health",
        "status": status,
        "command": "python3 ops/check_pool_data_health.py",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"],
        "reason": "" if status == "pass" else f"health check failed: rc={rc}",
    }


def step_post_run_guardrails(args, run_state):
    """最后一道事实护栏：真实赔率存在时，0 有效下注不能算完成。"""
    provider = run_state.get("odds_provider") or _resolve_odds_provider(args.odds_provider)
    real_path = _odds_snapshot_path(args.date, "T-1h", "the_odds_api")
    chosen_path = _odds_snapshot_path(args.date, "T-1h", provider)
    real_snapshot = _load_json(real_path, default={}) or {}
    chosen_snapshot = _load_json(chosen_path, default={}) or {}
    real_summary = real_snapshot.get("summary", {}) if isinstance(real_snapshot, dict) else {}
    chosen_summary = chosen_snapshot.get("summary", {}) if isinstance(chosen_snapshot, dict) else {}
    real_valid = int(real_summary.get("valid_odds_rows") or 0)
    chosen_valid = int(chosen_summary.get("valid_odds_rows") or 0)

    bet_receipts = _load_json(DATA_DIR / "bet_receipts" / f"{args.round_id}.json", default={}) or {}
    br_summary = bet_receipts.get("summary", {}) if isinstance(bet_receipts, dict) else {}
    readiness = _load_json(DATA_DIR / "reports" / f"settlement_readiness_{args.round_id}.json", default={}) or {}
    accepted_bets = int(br_summary.get("accepted_bets") or 0)
    provider_covered_accepted_bets = int(
        readiness.get("provider_covered_accepted_bets")
        or br_summary.get("provider_covered_accepted_bets")
        or 0
    )
    candidate_bets = int(br_summary.get("candidate_bets") or 0)

    report = _load_json(DATA_DIR / "daily_reports" / f"{args.date}_{args.round_id}.json", default={}) or {}
    blocking_gaps = [
        g for g in report.get("data_gaps", [])
        if g.get("blocking") is True or g.get("blocks")
    ] if isinstance(report, dict) else []

    prompt_dir = DATA_DIR / "prompts" / args.round_id
    stale_prompt_count = 0
    if prompt_dir.exists():
        for p in prompt_dir.glob("*.md"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            if '"provider": "manual_stub"' in text and '"valid_odds_rows": 0' in text:
                stale_prompt_count += 1

    warnings_list = []
    blockers = []
    if provider == "manual_stub":
        warnings_list.append("manual_stub_provider_used: daily model prompts were not backed by real odds")
    if stale_prompt_count:
        warnings_list.append(f"stale_zero_odds_prompts={stale_prompt_count}")
    if blocking_gaps:
        warnings_list.append(f"daily_report_blocking_gaps={len(blocking_gaps)}")

    if real_valid > 0 and provider_covered_accepted_bets == 0:
        blockers.append(
            "real_odds_present_but_no_provider_covered_accepted_bets: regenerate provider-covered prompts and recollect web model outputs"
        )
    elif chosen_valid <= 0 and provider != "manual_stub":
        blockers.append("real_provider_selected_but_no_valid_odds_rows")

    status = "blocked" if blockers else ("pass_with_warnings" if warnings_list else "pass")
    reason = "; ".join(blockers) if blockers else ("; ".join(warnings_list) if warnings_list else "")
    if blockers:
        run_state["hard_blocked"] = True

    stdout = (
        f"provider={provider}\n"
        f"chosen_valid_odds_rows={chosen_valid}\n"
        f"real_valid_odds_rows={real_valid}\n"
        f"accepted_bets={accepted_bets}\n"
        f"provider_covered_accepted_bets={provider_covered_accepted_bets}\n"
        f"candidate_bets={candidate_bets}\n"
        f"eligible_board_rows={readiness.get('eligible_board_rows', run_state.get('eligible_board_rows', 0))}\n"
        f"stale_zero_odds_prompts={stale_prompt_count}\n"
        f"blocking_gaps={len(blocking_gaps)}\n"
    )

    return {
        "step": "post_run_guardrails",
        "status": status,
        "command": "inspect odds/prompts/bet_receipts/daily_report",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": 0,
        "stdout_tail": _tail(stdout),
        "stderr_tail": "",
        "outputs": [],
        "warnings": warnings_list,
        "reason": reason,
    }


def step_deploy(args, run_state):
    """可选的 Vercel 部署步骤。"""
    if run_state.get("hard_blocked"):
        return {
            "step": "deploy",
            "status": "skipped",
            "command": "vercel --prod (--blocked by post_run_guardrails)",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "outputs": [],
            "warnings": [],
            "reason": "post_run_guardrails blocked this run; deploy skipped",
        }
    if not args.deploy:
        return {
            "step": "deploy",
            "status": "skipped",
            "command": "vercel --prod (--deploy not set)",
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "outputs": [],
            "warnings": [],
            "reason": "deploy not requested (use --deploy to enable)",
        }

    cmd = ["vercel", "--prod"]
    rc, out, err, dur = _run_cmd(cmd, dry_run=args.dry_run, timeout=120)

    status = "pass" if rc == 0 else "failed"

    return {
        "step": "deploy",
        "status": status,
        "command": "vercel --prod",
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "duration_ms": dur,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "outputs": [],
        "warnings": [] if rc == 0 else [f"returncode={rc}"],
        "reason": "" if status == "pass" else f"deploy failed: rc={rc}",
    }


# ── 步骤调度映射 ──────────────────────────────────────────────────────────────
STEP_FUNCTIONS = {
    "preflight":              step_preflight,
    "sync_matches":           step_sync_matches,
    "sync_results":           step_sync_results,
    "sync_odds_snapshots":    step_sync_odds_snapshots,
    "generate_eligible_board": step_generate_eligible_board,
    "generate_prompts":       step_generate_prompts,
    "ingest":                 step_ingest,
    "classify_model_output":  step_classify_model_output,
    "validate_model_outputs": step_validate_model_outputs,
    "settle_pool_round":      step_settle_pool_round,
    "rerun_failed_seats":     step_rerun_failed_seats,
    "generate_daily_report":  step_generate_daily_report,
    "check_data_health":      step_check_data_health,
    "post_run_guardrails":    step_post_run_guardrails,
    "deploy":                 step_deploy,
}


# ── 主流水线 ──────────────────────────────────────────────────────────────────

def run_pipeline(args):
    print("=" * 70)
    print("  AI Judge Daily Pool Pipeline  (P12.0)")
    print(f"  date:       {args.date}")
    print(f"  round_id:   {args.round_id}")
    print(f"  dry_run:    {args.dry_run}")
    print(f"  odds_provider: {_resolve_odds_provider(args.odds_provider)}")
    print(f"  skip_browser: {args.skip_browser}")
    print(f"  continue_on_warning: {args.continue_on_warning}")
    print(f"  deploy:     {args.deploy}")
    print("=" * 70)
    print()

    # 运行状态
    run_state = {"ingest_outputs_found": 0}

    # 执行所有步骤
    steps = []
    blockers = []
    warnings = []
    generated_files = []

    for step_name in STEPS_ORDER:
        fn = STEP_FUNCTIONS.get(step_name)
        if not fn:
            continue

        step_result = fn(args, run_state)
        steps.append(step_result)

        status = step_result["status"]
        reason = step_result.get("reason", "")

        # 收集警告
        for w in step_result.get("warnings", []):
            if w:
                warnings.append(w)

        # 收集生成文件
        for o in step_result.get("outputs", []):
            if o:
                generated_files.append(o)

        # 打印状态
        status_icon = {"pass": "✅", "skipped": "⏭️ ", "blocked": "🚫", "failed": "❌", "pass_with_warnings": "⚠️"}.get(status, "❓")
        print(f"  {status_icon} {step_name.ljust(22)} [{status}]")
        if reason:
            print(f"       ↳ {reason}")

        # blocker 处理
        if status == "blocked":
            blockers.append({"step": step_name, "reason": reason})
            if not args.continue_on_warning:
                print(f"\n  🛑 BLOCKER at {step_name}, stopping (use --continue-on-warning to proceed)")
                break
            print(f"       ⚠️  BLOCKER but continuing (--continue-on-warning set)")

        if status == "failed":
            if reason not in blockers:
                # "waiting_for_manual_ingest" is NOT a blocker, it's a warning
                is_waiting = "waiting_for_manual_ingest" in str(reason).lower() or "waiting_for_manual_ingest" in str(step_result.get("warnings", ""))
                if not is_waiting:
                    blockers.append({"step": step_name, "reason": reason})
            if not args.continue_on_warning:
                print(f"\n  🛑 FAILED step {step_name}, stopping (use --continue-on-warning to proceed)")
                break
            print(f"       ⚠️  FAILED but continuing (--continue-on-warning set)")

    print()

    # 汇总统计
    steps_passed = sum(1 for s in steps if s["status"] in ("pass", "pass_with_warnings"))
    steps_skipped = sum(1 for s in steps if s["status"] == "skipped")
    steps_failed = sum(1 for s in steps if s["status"] == "failed")
    steps_blocked = sum(1 for s in steps if s["status"] == "blocked")

    # 判定 final_status
    if any(s["status"] == "blocked" for s in steps):
        # filtered: real blockers (not waiting_for_manual_ingest)
        real_blockers = [
            s for s in steps
            if s["status"] == "blocked" and "waiting_for_manual_ingest" not in s.get("reason", "").lower() and "waiting_for_manual_ingest" not in str(s.get("warnings", ""))
        ]
        if real_blockers:
            final_status = "blocked"
        else:
            final_status = "pass_with_warnings"
    elif steps_failed > 0:
        final_status = "pass_with_warnings"
    elif len(warnings) > 0:
        final_status = "pass_with_warnings"
    else:
        final_status = "pass"

    # 构建报告
    pipeline_data = {
        "version": "p12.0",
        "date": args.date,
        "round_id": args.round_id,
        "generated_at": _now_iso(),
        "final_status": final_status,
        "dry_run": args.dry_run,
        "skip_browser": args.skip_browser,
        "summary": {
            "steps_total": len(steps),
            "steps_passed": steps_passed,
            "steps_skipped": steps_skipped,
            "steps_failed": steps_failed,
            "steps_blocked": steps_blocked,
            "blockers": len(blockers),
            "warnings": len(warnings),
        },
        "steps": steps,
        "blockers": blockers,
        "warnings": warnings,
        "generated_files": generated_files,
        "next_actions": _build_next_actions(steps, final_status, args),
    }

    # 输出 JSON
    if not args.dry_run:
        PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
        json_path = PIPELINE_DIR / f"{args.date}_{args.round_id}.json"
        md_path = PIPELINE_DIR / f"{args.date}_{args.round_id}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(pipeline_data, f, ensure_ascii=False, indent=2)
        print(f"   📄 Pipeline JSON: {json_path}")

        # 生成 Markdown
        md_content = _generate_markdown(pipeline_data, args)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"   📄 Pipeline MD:   {md_path}")

    else:
        print("   🔍 Dry run — no files written.")
        print()
        _print_dry_run_summary(steps)

    # 输出最终状态
    print()
    print(f"   final_status:  {final_status}")
    print(f"   passed:  {steps_passed}  skipped: {steps_skipped}  failed: {steps_failed}  blocked: {steps_blocked}")
    print(f"   blockers: {len(blockers)}  warnings: {len(warnings)}")
    print()

    return pipeline_data


def _build_next_actions(steps, final_status, args):
    """根据步骤结果生成 next_actions 列表。"""
    actions = []

    has_waiting = any(
        "waiting_for_manual_ingest" in s.get("reason", "").lower() or
        "waiting_for_manual_ingest" in str(s.get("warnings", ""))
        for s in steps
    )

    has_no_classify = any("skipped_no_classified_outputs" in s.get("reason", "") for s in steps)
    has_no_bets = any("skipped_no_bet_receipts" in s.get("reason", "") for s in steps)
    has_no_rerun = any("skipped_no_rerun_queue" in s.get("reason", "") for s in steps)

    if has_waiting:
        actions.append(f"waiting_for_manual_ingest: {args.round_id} 需要将模型原始输出放入 data/pool/model_outputs/raw/{args.round_id}/ 后重新运行 pipeline")
    if has_no_classify and not has_waiting:
        actions.append("re-run pipeline: classify_model_output step was skipped, re-run after raw outputs exist")
    if has_no_bets:
        actions.append("no bet receipts: bet_receipts/run-6.json 尚未生成, 等待模型输出分类后生成")
    if has_no_rerun:
        actions.append("no rerun queue: run-6 目前没有需要补跑的模型")

    if final_status == "pass":
        actions.append("pipeline completed successfully — ready for P12.1 scheduled/CI integration")
    elif final_status == "pass_with_warnings":
        actions.append("pipeline completed with warnings — review warnings above and re-run after manual steps complete")
    elif final_status == "blocked":
        actions.append(f"rerun_web_models_with_real_odds: 将 data/pool/prompts/{args.round_id}/*.md 重新发送给 12 个网页模型，保存到 data/pool/model_outputs/raw/{args.round_id}/ 后重新运行 pipeline")

    # Check for the daily report
    dr_step = next((s for s in steps if s["step"] == "generate_daily_report"), None)
    if dr_step and dr_step["status"] not in ("pass", "pass_with_warnings"):
        actions.append("daily report generation failed — investigate and re-run")

    # Vercel deploy
    if not args.deploy:
        actions.append("deploy: run with --deploy to push to Vercel, or run 'vercel --prod' manually")

    return actions


def _generate_markdown(data, args):
    """生成 pipeline run Markdown 报告。"""
    steps = data["steps"]
    summary = data["summary"]

    lines = []
    lines.append(f"# AI Judge Pipeline Run — {args.date} / {args.round_id}")
    lines.append("")
    lines.append(f"**Version:** {data['version']}")
    lines.append(f"**Generated:** {data['generated_at']}")
    lines.append(f"**Final Status:** {data['final_status']}")
    lines.append(f"**Dry Run:** {data['dry_run']}")
    lines.append("")

    # 1. 结论
    lines.append("## 1. 结论")
    lines.append("")
    if data["final_status"] == "pass":
        lines.append("Pipeline 全部步骤通过。")
    elif data["final_status"] == "pass_with_warnings":
        lines.append("Pipeline 完成，但有警告。")
        # Check for specific warnings
        for w in data.get("warnings", []):
            if "waiting_for_manual_ingest" in str(w).lower():
                lines.append("")
                lines.append(f"> **{args.round_id} 当前等待人工模型输出，不是 pipeline 失败。**")
                lines.append("> 人工将模型原始输出放入 `data/pool/model_outputs/raw/run-6/` 后重新运行 pipeline 即可。")
                break
    elif data["final_status"] == "blocked":
        lines.append("Pipeline 被 blocker 阻断。")
    lines.append("")

    # 2. 步骤状态
    lines.append("## 2. 步骤状态")
    lines.append("")
    lines.append("| Step | Status | Duration | Notes |")
    lines.append("|------|--------|----------|-------|")
    for s in steps:
        status_emoji = {"pass": "✅", "skipped": "⏭️", "blocked": "🚫", "failed": "❌", "pass_with_warnings": "⚠️"}.get(s["status"], "❓")
        dur_str = f"{s['duration_ms']}ms" if s["duration_ms"] else "-"
        note = s.get("reason", "")[:60] if s.get("reason") else "-"
        lines.append(f"| {s['step']} | {status_emoji} {s['status']} | {dur_str} | {note} |")
    lines.append("")

    # 3. 跳过原因
    lines.append("## 3. 跳过原因")
    lines.append("")
    skipped = [s for s in steps if s["status"] == "skipped"]
    if skipped:
        for s in skipped:
            reason = s.get("reason", "unknown")
            lines.append(f"- **{s['step']}**: {reason}")
    else:
        lines.append("无跳过的步骤。")
    lines.append("")

    # 4. Blockers
    lines.append("## 4. Blockers")
    lines.append("")
    if data.get("blockers"):
        for b in data["blockers"]:
            lines.append(f"- **{b['step']}**: {b['reason']}")
    else:
        lines.append("无 blockers。")
    lines.append("")

    # 5. Warnings
    lines.append("## 5. Warnings")
    lines.append("")
    if data.get("warnings"):
        for w in data["warnings"]:
            lines.append(f"- {w}")
    else:
        lines.append("无 warnings。")
    lines.append("")

    # 6. 生成文件
    lines.append("## 6. 生成文件")
    lines.append("")
    if data.get("generated_files"):
        for gf in data["generated_files"]:
            lines.append(f"- `{gf}`")
    else:
        lines.append("无文件生成。")
    lines.append("")

    # 7. 下一步动作
    lines.append("## 7. 下一步动作")
    lines.append("")
    if data.get("next_actions"):
        for na in data["next_actions"]:
            lines.append(f"- {na}")
    else:
        lines.append("- 待定。")
    lines.append("")

    return "\n".join(lines)


def _print_dry_run_summary(steps):
    """打印 dry-run 摘要。"""
    will_run = [s["step"] for s in steps if s["status"] in ("pass", "pass_with_warnings", "failed")]
    will_skip = [s["step"] for s in steps if s["status"] == "skipped"]
    will_block = [s["step"] for s in steps if s["status"] == "blocked"]

    print(f"   steps_total: {len(steps)}")
    if will_run:
        print(f"   will_run: {', '.join(will_run)}")
    if will_skip:
        print(f"   will_skip: {', '.join(will_skip)}")
    if will_block:
        print(f"   will_block: {', '.join(will_block)}")
    print(f"   no files written")


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="P12.0 AI Judge Daily Pool Pipeline — 一键串联全部子脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --dry-run
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --skip-browser
  python3 ops/run_daily_pool_pipeline.py --date 2026-06-03 --round run-6 --deploy
        """,
    )
    parser.add_argument("--date", required=True, help="Pipeline date (YYYY-MM-DD)")
    parser.add_argument("--round", required=True, dest="round_id", help="Round ID (e.g. run-6)")
    parser.add_argument("--odds-provider", default="auto",
                        help="Odds provider for pipeline prompts: auto | manual_stub | the_odds_api")
    parser.add_argument("--reuse-existing-odds", action="store_true",
                        help="Reuse an existing odds snapshot instead of fetching during this run")
    parser.add_argument("--strict-real-provider", action="store_true",
                        help="Fail odds sync if the selected real provider is not configured")
    parser.add_argument("--dry-run", action="store_true", help="Dry run — 不写任何文件")
    parser.add_argument("--skip-browser", action="store_true", default=True, help="跳过浏览器采集 (默认启用)")
    parser.add_argument("--continue-on-warning", action="store_true", default=True, help="遇到 warning/blocker 继续执行 (默认启用)")
    parser.add_argument("--stop-on-error", action="store_true", help="遇到任何错误立即停止")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--deploy", action="store_true", default=False, help="执行后自动部署到 Vercel")

    args = parser.parse_args()

    # --stop-on-error 覆盖 --continue-on-warning
    if args.stop_on_error:
        args.continue_on_warning = False

    pipeline_data = run_pipeline(args)

    # 退出码
    if pipeline_data["final_status"] == "blocked":
        sys.exit(1)
    elif pipeline_data["final_status"] == "failed":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
