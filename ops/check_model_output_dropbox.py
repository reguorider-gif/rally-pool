#!/usr/bin/env python3
"""
P13.0 Model Output Dropbox Checker — 检查 run-6 模型输出投喂目录状态。

用法:
  python3 ops/check_model_output_dropbox.py --round run-6
  python3 ops/check_model_output_dropbox.py --round run-6 --json

输出:
  data/pool/model_outputs/raw/run-6/dropbox_check.json

状态枚举:
  - waiting_for_manual_ingest : 0 个文件
  - partial_outputs_found      : 1–12 个文件
  - ready_for_ingest          : 13 个文件（完整）
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 路径 ───────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "pool"


def load_model_accounts() -> list:
    """读取 model_accounts/current.json，返回 model_account 列表。"""
    p = DATA_DIR / "model_accounts" / "current.json"
    if not p.exists():
        print(f"  [error] model_accounts/current.json not found", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return [m["model_account"] for m in data.get("models", [])]


def check_dropbox(round_id: str, to_json: bool = False):
    """检查指定 round 的 raw output 投喂目录。"""
    raw_dir   = DATA_DIR / "model_outputs" / "raw" / round_id
    out_path  = raw_dir / "dropbox_check.json"
    accounts  = load_model_accounts()
    expected  = set(accounts)
    found     = []
    missing   = []
    empty     = []
    mismatched = []

    print(f"=== Model Output Dropbox Check: {round_id} ===")
    print(f"  expected models : {len(accounts)}")
    print(f"  raw dir         : {raw_dir}")

    if not raw_dir.exists():
        print(f"  [status] raw dir does not exist → waiting_for_manual_ingest")
        result = {
            "version":          "p13.0",
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "round_id":         round_id,
            "outputs_expected":  len(accounts),
            "outputs_found":    0,
            "outputs_missing":   len(accounts),
            "found_files":      [],
            "missing_files":    [f"{a}.txt" for a in accounts],
            "empty_files":      [],
            "mismatched_files": [],
            "status":           "waiting_for_manual_ingest",
            "message":          f"Raw dir not found. Create {raw_dir} and drop model outputs there.",
            "next_action":      f"mkdir -p {raw_dir} && # then drop <model_account>.txt files",
        }
        if to_json:
            print("\n" + json.dumps(result, ensure_ascii=False, indent=2))
        return result

    # 扫描目录
    for f in sorted(raw_dir.iterdir()):
        if not f.is_file() or f.suffix != ".txt":
            continue
        name = f.stem  # model_account
        size = f.stat().st_size

        if name not in expected:
            mismatched.append({"file": f.name, "reason": "not_in_model_accounts"})
            continue

        if size == 0:
            empty.append(f.name)

        found.append(name)

    found_set = set(found)
    missing    = sorted(expected - found_set)

    # 判断状态
    n_found = len(found)
    if n_found == 0:
        status = "waiting_for_manual_ingest"
    elif n_found < len(accounts):
        status = "partial_outputs_found"
    else:
        status = "ready_for_ingest"

    result = {
        "version":          "p13.0",
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "round_id":         round_id,
        "outputs_expected":  len(accounts),
        "outputs_found":    n_found,
        "outputs_missing":   len(missing),
        "found_files":      sorted(found),
        "missing_files":    missing,
        "empty_files":      empty,
        "mismatched_files": mismatched,
        "status":           status,
        "message":          _status_message(status, n_found, len(accounts)),
        "next_action":      _next_action(status, round_id, missing),
    }

    # 终端输出
    print(f"  found           : {n_found}/{len(accounts)}")
    print(f"  missing         : {len(missing)}")
    print(f"  empty files     : {len(empty)}")
    print(f"  mismatched      : {len(mismatched)}")
    print(f"  [status] {status}")
    print(f"  message: {result['message']}")
    if result["next_action"]:
        print(f"  next: {result['next_action']}")

    # 写 JSON
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  [write] {out_path.relative_to(BASE_DIR)}")

    if to_json:
        print("\n" + json.dumps(result, ensure_ascii=False, indent=2))

    return result


def _status_message(status: str, found: int, expected: int) -> str:
    if status == "waiting_for_manual_ingest":
        return (
            f"No model outputs found. "
            f"Drop raw model outputs as <model_account>.txt into the raw dir."
        )
    if status == "partial_outputs_found":
        return (
            f"Partial outputs found ({found}/{expected}). "
            f"You can run partial ingest, or wait for all outputs."
        )
    return (
        f"All {expected} model outputs found. "
        f"Ready to run: python3 ops/ai_judge_daily_pool.py ingest --round {expected}"
    )


def _next_action(status: str, round_id: str, missing: list) -> str:
    if status == "waiting_for_manual_ingest":
        return f"# drop model output .txt files into data/pool/model_outputs/raw/{round_id}/"
    if status == "partial_outputs_found":
        return (
            f"# partial ingest:\n"
            f"  python3 ops/ai_judge_daily_pool.py ingest --round {round_id} "
            f"--input-dir data/pool/model_outputs/raw/{round_id}"
        )
    return (
        f"python3 ops/ai_judge_daily_pool.py ingest "
        f"--round {round_id} "
        f"--input-dir data/pool/model_outputs/raw/{round_id}"
    )


def main():
    parser = argparse.ArgumentParser(description="P13.0 Model Output Dropbox Checker")
    parser.add_argument("--round",   default="run-6", help="Round ID (default: run-6)")
    parser.add_argument("--json",     action="store_true", help="Also print JSON to stdout")
    args = parser.parse_args()

    check_dropbox(round_id=args.round, to_json=args.json)


if __name__ == "__main__":
    main()
