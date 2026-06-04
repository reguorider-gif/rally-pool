"""
P13.0B - 模型输出投喂检查。

扫描 data/pool/model_outputs/raw/{round_id}/ 目录，
生成 dropbox_check.json 报告，供 generate_daily_pool_report.py 读取。

不做任何分类/校验，只报告发现状态。
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ---- 路径 ----
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "pool"
DROPBOX_REPORTS_DIR = DATA_DIR / "model_outputs" / "dropbox_reports"
DROPBOX_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_expected_models() -> list[str]:
    accounts_path = DATA_DIR / "model_accounts" / "current.json"
    if not accounts_path.exists():
        return [
            "chatgpt", "deepseek", "doubao", "gemini",
            "kimi", "meta", "mimo", "minimax",
            "qwen", "wenxin", "xai", "yuanbao",
        ]
    data = json.loads(accounts_path.read_text(encoding="utf-8"))
    return [
        str(item.get("model_account") or item.get("seat_id"))
        for item in data.get("models", [])
        if item.get("model_account") or item.get("seat_id")
    ]


def check_dropbox(round_id: str, input_dir: Path = None) -> dict:
    """检查模型输出投喂目录状态。"""
    if input_dir is None:
        input_dir = DATA_DIR / "model_outputs" / "raw" / round_id

    expected_models = load_expected_models()

    found_files = []
    missing_files = []
    empty_files = []
    mismatched_files = []

    for model in expected_models:
        txt_path = input_dir / f"{model}.txt"
        if txt_path.exists():
            size = txt_path.stat().st_size
            if size == 0:
                empty_files.append(model)
            else:
                found_files.append(model)
        else:
            missing_files.append(model)

    outputs_found = len(found_files)
    outputs_expected = len(expected_models)
    outputs_missing = len(missing_files)

    # 五态判断
    if outputs_found == 0:
        status = "waiting_for_manual_ingest"
        message = "No model outputs found. Drop raw model outputs as <model_account>.txt into the raw dir."
        next_action = f"# drop model output .txt files into {input_dir}/"
    elif 0 < outputs_found < outputs_expected:
        status = "partial_outputs_found"
        message = f"Partial model outputs found: {outputs_found}/{outputs_expected}."
        next_action = f"# still missing: {', '.join(missing_files)}"
    else:
        status = "ready_for_ingest"
        message = f"All {outputs_expected} model outputs found. Ready for ingest."
        next_action = f"python3 ops/ai_judge_daily_pool.py ingest --round {round_id}"

    report = {
        "version": "p13.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round_id": round_id,
        "outputs_expected": outputs_expected,
        "outputs_found": outputs_found,
        "outputs_missing": outputs_missing,
        "found_files": found_files,
        "missing_files": missing_files,
        "empty_files": empty_files,
        "mismatched_files": mismatched_files,
        "status": status,
        "message": message,
        "next_action": next_action,
    }

    # 同时写入 raw 目录（供 generate_daily_pool_report.py 读取）
    dropbox_check_path = input_dir / "dropbox_check.json"
    dropbox_check_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入 dropbox_reports 目录（供 API 读取）
    report_path = DROPBOX_REPORTS_DIR / f"{round_id}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report


def main():
    parser = argparse.ArgumentParser(description="P13.0B 模型输出投喂检查")
    parser.add_argument("--round", required=True, help="round id, e.g. run-6")
    parser.add_argument(
        "--input-dir",
        default=None,
        help="override input dir (default: data/pool/model_outputs/raw/{round_id}/)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir) if args.input_dir else None
    report = check_dropbox(args.round, input_dir)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        f"\n[ingest_run6_outputs] status={report['status']}, "
        f"found={report['outputs_found']}/{report['outputs_expected']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
