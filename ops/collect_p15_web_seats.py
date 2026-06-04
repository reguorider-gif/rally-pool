#!/usr/bin/env python3
"""
P15 fixed-CDP web-seat collector adapter.

This adapter connects the pool-app run-7 prompt/dropbox chain to the formal
AI Judge fixed Chrome CDP runner that lives one directory above pool-app. It
only saves raw outputs returned by real web seats. Failed seats are recorded in
provenance and rerun ledgers; no placeholder is promoted to model output.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
AI_JUDGE_DIR = ROOT_DIR.parent
DATA_DIR = ROOT_DIR / "data" / "pool"
RUNNER_PATH = AI_JUDGE_DIR / "web_council_runner.py"

ACTIVE_SEATS = [
    "gemini",
    "chatgpt",
    "yuanbao",
    "wenxin",
    "deepseek",
    "mimo",
    "kimi",
    "qwen",
    "xai",
    "minimax",
    "doubao",
    "meta",
]
SUCCESS_STATUSES = {"answered", "raw_answer_unparsed"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_runner():
    if not RUNNER_PATH.exists():
        raise FileNotFoundError(f"fixed CDP runner not found: {RUNNER_PATH}")
    spec = importlib.util.spec_from_file_location("web_council_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import fixed CDP runner: {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["web_council_runner"] = module
    spec.loader.exec_module(module)
    return module


def load_active_seats() -> list[str]:
    accounts = load_json(DATA_DIR / "model_accounts" / "current.json", {})
    seats = [
        str(m.get("model_account"))
        for m in accounts.get("models", [])
        if m.get("status") == "active" and m.get("model_account")
    ]
    return seats or ACTIVE_SEATS[:]


def load_prompts(round_id: str, seats: list[str]) -> dict[str, str]:
    prompt_dir = DATA_DIR / "prompts" / round_id
    prompts: dict[str, str] = {}
    missing: list[str] = []
    for seat in seats:
        path = prompt_dir / f"{seat}.md"
        if not path.exists():
            missing.append(seat)
            continue
        prompts[seat] = path.read_text(encoding="utf-8")
    if missing:
        raise FileNotFoundError(f"missing prompts for seats: {', '.join(missing)}")
    return prompts


def build_metadata(round_id: str, date: str, seats: list[str]) -> dict:
    return {
        "run_id": round_id,
        "round_id": round_id,
        "date": date,
        "question": f"P15 provider-covered rerun for {round_id}",
        "created_at": now_iso(),
        "status": "collecting",
        "total_seats": len(seats),
        "active_pool_models": seats,
        "collector": "ops/collect_p15_web_seats.py",
        "policy": {
            "web_only": True,
            "fixed_cdp": "http://127.0.0.1:9333",
            "no_mock_outputs": True,
            "disabled_active_seats": ["claude", "zhipu"],
            "prompt_truncation": "disabled",
        },
    }


def raw_output_is_real(text: str | None) -> bool:
    if not text or len(text.strip()) <= 50:
        return False
    return not text.lstrip().startswith("[WAITING")


def export_to_pool(round_id: str, date: str, run_dir: Path, rows: list[dict], seats: list[str]) -> dict:
    raw_dir = DATA_DIR / "model_outputs" / "raw" / round_id
    provenance_dir = DATA_DIR / "model_outputs" / "provenance" / round_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    provenance_dir.mkdir(parents=True, exist_ok=True)

    saved: list[dict] = []
    blocked: list[dict] = []
    saved_by_seat: set[str] = set()

    for row in rows:
        seat = str(row.get("seat_id") or row.get("seat") or "")
        if not seat:
            continue
        raw_text = row.get("raw_text") or ""
        status = row.get("status") or "unknown"
        failure_reason = row.get("failure_reason") or row.get("reason") or status
        raw_rel = f"data/pool/model_outputs/raw/{round_id}/{seat}.txt"
        seat_provenance_path = provenance_dir / f"{seat}.json"

        ok = status in SUCCESS_STATUSES and raw_output_is_real(raw_text)
        if ok:
            raw_path = raw_dir / f"{seat}.txt"
            raw_path.write_text(raw_text, encoding="utf-8")
            saved_by_seat.add(seat)
            saved.append({
                "seat_id": seat,
                "status": status,
                "path": str(raw_path),
                "raw_output_path": raw_rel,
                "bytes": raw_path.stat().st_size,
                "response_chars": len(raw_text),
            })
        else:
            attempts = row.get("attempts") or []
            body_excerpt = ""
            if attempts and isinstance(attempts[-1], dict):
                preflight = attempts[-1].get("preflight") or {}
                body_excerpt = str(preflight.get("body_excerpt") or attempts[-1].get("raw_text_excerpt") or "")
            blocked.append({
                "seat_id": seat,
                "status": status,
                "failure_reason": failure_reason,
                "attempts": attempts,
                "body_excerpt": body_excerpt[:1600],
            })

        write_json(seat_provenance_path, {
            "version": "p15_fixed_cdp_web_collection.v1",
            "run_id": row.get("run_id") or round_id,
            "round_id": round_id,
            "date": date,
            "seat": seat,
            "model_account": seat,
            "ok": ok,
            "status": status,
            "failure_reason": failure_reason,
            "method": "fixed_chrome_cdp_web_runner",
            "raw_output_path": raw_rel if ok else None,
            "parsed": row.get("parsed") if isinstance(row.get("parsed"), dict) else None,
            "response_chars": len(raw_text or ""),
            "attempts": row.get("attempts") or [],
            "source_run_dir": str(run_dir),
        })

    missing_rows = []
    for seat in seats:
        if seat in saved_by_seat or any(b.get("seat_id") == seat for b in blocked):
            continue
        missing_rows.append({
            "seat_id": seat,
            "status": "not_returned_by_collector",
            "failure_reason": "collector_return_missing_seat",
            "attempts": [],
            "body_excerpt": "",
        })
    blocked.extend(missing_rows)

    sync = {
        "version": "p15_fixed_cdp_web_collection.v1",
        "run_id": round_id,
        "round_id": round_id,
        "date": date,
        "exported_at": now_iso(),
        "web_run_dir": str(run_dir),
        "total": len(seats),
        "saved_raw_outputs": len(saved),
        "blocked_or_missing": len(blocked),
        "saved": saved,
        "blocked": blocked,
        "rows": [
            {
                "seat_id": item["seat_id"],
                "source_file": str((provenance_dir / f"{item['seat_id']}.json")),
                "raw_output_path": item["raw_output_path"],
                "response_chars": item["response_chars"],
            }
            for item in saved
        ],
        "active_pool_models": seats,
    }
    write_json(provenance_dir / "web_collection_sync.json", sync)
    return sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect P15 pool prompts through fixed Chrome CDP web seats.")
    parser.add_argument("--round", required=True, dest="round_id", help="Round ID, e.g. run-7")
    parser.add_argument("--date", default="2026-06-03", help="Pool date")
    parser.add_argument("--seats", default=None, help="Comma-separated seat ids; defaults to active 12 seats")
    parser.add_argument("--run-dir", default=None, help="Optional external judge-runs directory")
    parser.add_argument("--allow-short-prompts", action="store_true", help="Allow legacy short-prompt truncation for fragile seats")
    args = parser.parse_args()

    seats = [s.strip() for s in args.seats.split(",") if s.strip()] if args.seats else load_active_seats()
    forbidden = {"claude", "zhipu"}
    seats = [s for s in seats if s not in forbidden]
    if len(seats) != 12:
        raise RuntimeError(f"P15 active seat count must be 12 after removing Claude/Zhipu; got {len(seats)}: {seats}")

    prompts = load_prompts(args.round_id, seats)
    runner = load_runner()
    runner.ensure_bridge()
    if not args.allow_short_prompts:
        runner.SHORT_PROMPT_SEATS = set()

    run_dir = Path(args.run_dir) if args.run_dir else runner.RUNS_DIR / f"pool-p15-{args.round_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "metadata.json", build_metadata(args.round_id, args.date, seats))

    print("collect_p15_web_seats")
    print(f"  round_id: {args.round_id}")
    print(f"  date:     {args.date}")
    print(f"  seats:    {len(seats)}")
    print(f"  run_dir:  {run_dir}")
    print("  policy:   fixed Chrome CDP, no mock outputs, Claude/Zhipu disabled")

    rows = runner.collect_many(prompts, run_dir, args.round_id, round_num=1)
    sync = export_to_pool(args.round_id, args.date, run_dir, rows, seats)

    print("collection summary")
    print(f"  saved_raw_outputs: {sync['saved_raw_outputs']}/{sync['total']}")
    print(f"  blocked_or_missing: {sync['blocked_or_missing']}")
    for blocked in sync["blocked"]:
        print(f"  - {blocked['seat_id']}: {blocked['status']} ({blocked['failure_reason']})")


if __name__ == "__main__":
    main()
