#!/usr/bin/env python3
"""
ops/rerun_failed_seats.py
P11.1 自动补跑机制

用法:
  python3 ops/rerun_failed_seats.py --round run-5 --dry-run
  python3 ops/rerun_failed_seats.py --round run-5 --generate-prompts-only
  python3 ops/rerun_failed_seats.py --round run-5 --max-attempts 3
  python3 ops/rerun_failed_seats.py --round run-5 --ingest --input-dir data/pool/model_outputs/raw_rerun/run-5/attempt-2
  python3 ops/rerun_failed_seats.py --round run-5 --status
  python3 ops/rerun_failed_seats.py --round run-6 --dry-run

职责:
  1. 读取已有 rerun_queue/<round>.json
  2. 判断哪些模型允许补跑
  3. 生成补跑计划和 attempt ledger
  4. 生成补跑专用 prompt
  5. 支持手工/外部补跑结果 ingest
  6. 不覆盖原始失败记录
  7. 不调用不稳定浏览器
  8. 不编造模型输出
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------- 项目根目录 ----------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "pool"

# ---------- 合规声明 ----------
COMPLIANCE_NOTICE = (
    "【合规与实验边界】\n"
    "这是虚拟 GP 预测研究，不涉及真钱下注，不构成现实博彩建议。\n"
    "所有投注均为模拟，仅用于算法研究与模型评估。"
)

# ---------- 允许/不允许补跑的状态 ----------
ALLOWED_RERUN_STATUSES = [
    "placeholder_only",
    "context_polluted",
    "quota_blocked",
    "auth_blocked",
    "timeout",
    "parse_error",
]

DISALLOWED_RERUN_STATUSES = [
    "valid_receipt",
    "risk_refusal",
    "excluded_from_consensus",
]


def _now_iso():
    """返回当前 UTC ISO 时间戳"""
    return datetime.now(timezone.utc).isoformat()


def _read_json(relative_path, default=None):
    """安全读取 JSON 文件"""
    full_path = DATA_DIR / relative_path
    if not full_path.exists():
        return default
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(relative_path, data, indent=2):
    """安全写入 JSON 文件"""
    full_path = DATA_DIR / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def _compact_json(value, max_chars=6000):
    """安全压缩 JSON 为字符串，超出截断。"""
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        text = json.dumps({"error": f"json serialization failed: {exc}"}, ensure_ascii=False)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...<truncated>"
    return text


def _build_rerun_marker(round_id, attempt_no, date_str):
    """构建 rerun marker"""
    date_clean = date_str.replace("-", "")
    round_clean = round_id.upper().replace("-", "_")
    return f"AI_JUDGE_RERUN_MARKER:POOL_{round_clean}_ATTEMPT_{attempt_no}_{date_clean}"


def _build_rerun_prompt(queue_entry, round_id, attempt_no, date_str, max_attempts,
                        matches, match_results, odds_snapshot, leaderboard, previous_report):
    """
    为单个失败模型构建补跑 prompt。
    使用 json.dumps() + "\n".join(lines) 避免格式化冲突。
    """
    model_account = queue_entry.get("model_account") or queue_entry.get("seat_id")
    seat_id = queue_entry.get("seat_id") or model_account
    current_status = queue_entry.get("current_status", "unknown")
    reason = queue_entry.get("reason", "")
    requires_quota = (current_status == "quota_blocked")
    requires_auth = (current_status == "auth_blocked")

    # ---------- JSON 示例 ----------
    example_empty_output = {
        "model_account": model_account,
        "round_id": round_id,
        "loan_decision": {"amount": 0, "reason": "No valid odds available."},
        "bet_ledger": [],
        "risk_rules": {"max_loss": 0, "stop_after_losses": 0},
        "source_cards": [],
        "betting_thought": "No valid bet because odds snapshot has no valid market coverage.",
    }

    strict_schema_example = {
        "model_account": model_account,
        "round_id": round_id,
        "loan_decision": {"amount": 0, "reason": ""},
        "bet_ledger": [{
            "match_id": "WARM-002",
            "market": "moneyline",
            "selection": "Brazil",
            "stake": 100,
            "odds": 1.85,
            "confidence": 0.6,
            "reason": "",
            "cancel_if": "",
        }],
        "risk_rules": {"max_loss": 500, "stop_after_losses": 2},
        "source_cards": [],
        "betting_thought": "",
    }

    # ---------- 数据摘要 ----------
    matches_list = []
    if isinstance(matches, dict):
        matches_list = matches.get("matches", [])
    elif isinstance(matches, list):
        matches_list = matches

    odds_summary_data = {
        "snapshot_label": odds_snapshot.get("snapshot_label") if isinstance(odds_snapshot, dict) else None,
        "provider": odds_snapshot.get("provider") if isinstance(odds_snapshot, dict) else None,
        "summary": odds_snapshot.get("summary") if isinstance(odds_snapshot, dict) else {},
        "warning": "If valid_odds_rows is 0, do not invent odds. Use empty bet_ledger.",
    }

    matches_summary = _compact_json({
        "matches_total": len(matches_list),
        "sample_matches": matches_list[:10],
    })
    results_summary = _compact_json(match_results)
    odds_summary = _compact_json(odds_summary_data)
    leaderboard_summary = _compact_json(leaderboard)
    previous_report_summary = _compact_json(previous_report)

    # ---------- 修复说明 ----------
    fix_section = []
    fix_section.append("## 上次输出无效原因")
    fix_section.append(f"previous_status: {current_status}")
    fix_section.append(f"previous_failure_reason: {reason}")
    fix_section.append("")
    fix_section.append("## 强制修正说明")
    fix_section.append("上一次输出无效。本次必须只输出标准 JSON 投注单。")
    fix_section.append("不要回答旧任务、狼人杀、验收报告或任何历史上下文。")
    fix_section.append("不要输出你的最终答案。")
    fix_section.append("不要输出 Markdown。")
    fix_section.append("不要输出解释性自然语言。")
    fix_section.append("不要输出 JSON 之外的任何内容。")
    fix_section.append("JSON 必须能被 json.loads 解析。")

    if requires_quota:
        fix_section.append("")
        fix_section.append(f"⚠️  注意: 当前模型状态为 {current_status}，需要配额可用后才能投注。")
    if requires_auth:
        fix_section.append("")
        fix_section.append(f"⚠️  注意: 当前模型状态为 {current_status}，需要刷新认证后才能投注。")

    # ---------- 拼接 ----------
    run_marker = _build_rerun_marker(round_id, attempt_no, date_str)
    lines = [
        f"AI_JUDGE_RERUN_MARKER:{run_marker}",
        "",
        "# AI Judge 赛事预测池 — 补跑任务",
        "",
        f"round_id: {round_id}",
        f"attempt_no: {attempt_no}",
        f"max_attempts: {max_attempts}",
        f"seat_id: {seat_id}",
        f"model_account: {model_account}",
        f"date: {date_str}",
        "",
        COMPLIANCE_NOTICE,
        "",
    ] + fix_section + [
        "",
        "# 本次任务",
        "你是 AI Judge 赛事预测池中的一个独立模型席位。",
        "请基于以下赛程、赛果状态、赔率快照、资金风控约束，输出结构化 JSON 投注单。",
        "",
        "## 可用比赛摘要",
        matches_summary,
        "",
        "## 赛果状态摘要",
        results_summary,
        "",
        "## 赔率快照摘要",
        odds_summary,
        "",
        "## 当前排行榜/账户摘要",
        leaderboard_summary,
        "",
        "## 上一轮日报摘要",
        previous_report_summary,
        "",
        "## 标准 JSON schema 示例",
        json.dumps(strict_schema_example, ensure_ascii=False, indent=2),
        "",
        "## 如果没有有效赔率或没有可下注机会，必须输出以下结构",
        json.dumps(example_empty_output, ensure_ascii=False, indent=2),
        "",
        "【强制输出格式】",
        "你必须只输出一个 JSON 对象。",
        "JSON 顶层必须包含：",
        "- model_account",
        "- round_id",
        "- loan_decision",
        "- bet_ledger",
        "- risk_rules",
        "- source_cards",
        "- betting_thought",
        "",
        "禁止输出任何 JSON 之外的内容。",
    ]

    return "\n".join(lines)


def _plan_rerun_from_queue(round_id, max_attempts, dry_run=False, verbose=False):
    """
    从 rerun_queue 读取并生成补跑计划。
    返回:
      - plan: dict (attempt ledger 结构)
      - queue_data: dict (原始 queue 数据)
      - date_str: str
    """
    queue_data = _read_json(f"rerun_queue/{round_id}.json", default=None)
    if queue_data is None:
        print(f"round_id: {round_id}")
        print("state: no_rerun_queue")
        print("action: wait_for_initial_classification")
        return None, None, None

    queue = queue_data.get("queue", [])
    if not queue:
        print(f"round_id: {round_id}")
        print("state: empty_rerun_queue")
        print("action: no failed seats to rerun")
        return None, queue_data, None

    # 从 run_manifest 推断 date_str
    manifest = _read_json(f"run_manifests/{round_id}.json", default=None)
    date_str = manifest.get("date", "2026-06-03") if manifest else "2026-06-03"

    attempts = []
    skipped = 0
    planned = 0

    for entry in queue:
        status = entry.get("current_status", "")
        model_account = entry.get("model_account") or entry.get("seat_id")
        seat_id = entry.get("seat_id") or model_account
        attempt_no = entry.get("next_attempt_no", 2)

        if status in DISALLOWED_RERUN_STATUSES:
            if verbose:
                print(f"  SKIP {model_account}: status={status} not allowed for rerun")
            skipped += 1
            continue

        if status not in ALLOWED_RERUN_STATUSES:
            if verbose:
                print(f"  SKIP {model_account}: status={status} unknown, treating as disallowed")
            skipped += 1
            continue

        requires_quota = (status == "quota_blocked")
        requires_auth = (status == "auth_blocked")

        attempts.append({
            "model_account": model_account,
            "seat_id": seat_id,
            "source_status": status,
            "previous_failure_reason": entry.get("reason", ""),
            "attempt_no": attempt_no,
            "max_attempts": max_attempts,
            "state": "planned",
            "prompt_path": f"prompts/rerun/{round_id}/attempt-{attempt_no}/{model_account}.md",
            "raw_output_path": f"model_outputs/raw_rerun/{round_id}/attempt-{attempt_no}/{model_account}.txt",
            "ingested_output_path": "",
            "requires_auth_refresh": requires_auth,
            "requires_quota_available": requires_quota,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        })
        planned += 1

    plan = {
        "version": "p11.1",
        "round_id": round_id,
        "generated_at": _now_iso(),
        "max_attempts": max_attempts,
        "summary": {
            "queue_total": len(queue),
            "planned_attempts": planned,
            "skipped": skipped,
            "completed": 0,
            "failed": 0,
            "state": "planned",
        },
        "attempts": attempts,
        "date": date_str,
    }

    return plan, queue_data, date_str


def cmd_plan(args):
    """只生成补跑计划（dry-run 或生成 attempt ledger）"""
    round_id = args.round
    max_attempts = args.max_attempts or 3
    dry_run = args.dry_run
    verbose = args.verbose

    plan, queue_data, date_str = _plan_rerun_from_queue(round_id, max_attempts, dry_run, verbose)

    if plan is None:
        return

    summary = plan["summary"]
    print("rerun_failed_seats")
    print(f"round_id: {round_id}")
    print(f"queue_total: {summary['queue_total']}")
    print(f"planned_attempts: {summary['planned_attempts']}")
    print(f"skipped: {summary['skipped']}")
    print(f"dry_run: {dry_run}")

    if dry_run:
        print("no files written")
        return

    # 写入 attempt ledger
    _write_json(f"rerun_attempts/{round_id}.json", plan)
    print(f"  ✅ Attempt ledger: data/pool/rerun_attempts/{round_id}.json")
    print()

    if verbose:
        for a in plan["attempts"]:
            print(f"  [{a['model_account']}] status={a['source_status']} attempt={a['attempt_no']}")


def cmd_generate_prompts(args):
    """生成补跑 attempt ledger 和 prompts"""
    round_id = args.round
    max_attempts = args.max_attempts or 3
    dry_run = args.dry_run
    verbose = args.verbose

    plan, queue_data, date_str = _plan_rerun_from_queue(round_id, max_attempts, dry_run, verbose)

    if plan is None:
        return

    summary = plan["summary"]
    print("rerun_failed_seats")
    print(f"round_id: {round_id}")
    print(f"queue_total: {summary['queue_total']}")
    print(f"planned_attempts: {summary['planned_attempts']}")
    print(f"skipped: {summary['skipped']}")

    if dry_run:
        print("dry_run: true")
        print("no files written")
        return

    # 写入 attempt ledger
    _write_json(f"rerun_attempts/{round_id}.json", plan)
    print(f"  ✅ Attempt ledger: data/pool/rerun_attempts/{round_id}.json")

    if summary["planned_attempts"] == 0:
        print("  ⚠️  No seats to rerun, skipping prompt generation")
        return

    # 预加载数据源
    matches_data = _read_json("matches/current.json", default={})
    match_results_data = _read_json(f"match_results/{date_str}.json", default={})
    odds_data = _read_json(f"odds_snapshots/{date_str}_T-1h.json", default={})
    leaderboard_data = _read_json("leaderboard/current.json", default={})
    # 尝试找对应 round 的日报告
    prev_report_data = {}
    for attempt_round in ["run-5", "run-6", "run-4"]:
        prev_report_data = _read_json(f"daily_reports/{date_str}_{attempt_round}.json", default=None)
        if prev_report_data:
            break
    if prev_report_data is None:
        prev_report_data = {}

    # 生成补跑 prompts
    for a in plan["attempts"]:
        # 在 queue 中找对应条目
        queue_entry = None
        for q in (queue_data.get("queue", []) if queue_data else []):
            if q.get("model_account") == a["model_account"] or q.get("seat_id") == a["model_account"]:
                queue_entry = q
                break
        if queue_entry is None:
            queue_entry = {
                "model_account": a["model_account"],
                "seat_id": a["seat_id"],
                "current_status": a["source_status"],
                "reason": a["previous_failure_reason"],
                "next_attempt_no": a["attempt_no"],
            }

        prompt = _build_rerun_prompt(
            queue_entry=queue_entry,
            round_id=round_id,
            attempt_no=a["attempt_no"],
            date_str=date_str,
            max_attempts=max_attempts,
            matches=matches_data,
            match_results=match_results_data,
            odds_snapshot=odds_data,
            leaderboard=leaderboard_data,
            previous_report=prev_report_data,
        )

        prompt_rel = f"prompts/rerun/{round_id}/attempt-{a['attempt_no']}/{a['model_account']}.md"
        prompt_dir = DATA_DIR / "prompts" / "rerun" / round_id / f"attempt-{a['attempt_no']}"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompt_dir / f"{a['model_account']}.md"
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        if verbose:
            print(f"  ✅ Prompt: {prompt_rel}")

    print(f"  ✅ Generated {summary['planned_attempts']} rerun prompts in data/pool/prompts/rerun/{round_id}/attempt-{plan['attempts'][0]['attempt_no']}")
    print()

    print("PROMPTS GENERATED — 请手动将补跑 prompt 发送给各模型，并保存原始输出到:")
    raw_dir = DATA_DIR / "model_outputs" / "raw_rerun" / round_id / f"attempt-{plan['attempts'][0]['attempt_no']}"
    print(f"  {raw_dir}")
    print()
    print("完成后运行:")
    print(f"  python3 ops/rerun_failed_seats.py --round {round_id} --ingest --input-dir data/pool/model_outputs/raw_rerun/{round_id}/attempt-{plan['attempts'][0]['attempt_no']}")


def cmd_ingest(args):
    """Ingest 补跑原始输出"""
    round_id = args.round
    input_dir = Path(args.input_dir).resolve()
    verbose = args.verbose

    print("rerun_failed_seats ingest")
    print(f"round_id: {round_id}")
    print(f"input_dir: {input_dir}")
    print()

    if not input_dir.exists():
        print(f"ERROR: input_dir not found: {input_dir}")
        sys.exit(1)

    # 从目录名推断 attempt_no
    attempt_no = 2
    dir_name = input_dir.name
    if dir_name.startswith("attempt-"):
        try:
            attempt_no = int(dir_name.split("-")[1])
        except (ValueError, IndexError):
            pass

    # 读取 attempt ledger 获取期望的模型列表
    ledger = _read_json(f"rerun_attempts/{round_id}.json", default=None)
    expected_models = []
    if ledger:
        for a in ledger.get("attempts", []):
            if a.get("attempt_no") == attempt_no:
                expected_models.append(a.get("model_account") or a.get("seat_id"))

    if not expected_models:
        # 从文件系统推断
        txt_files = sorted(input_dir.glob("*.txt"))
        expected_models = [tf.stem for tf in txt_files]

    outputs = []
    outputs_found = 0

    for model in expected_models:
        raw_path = input_dir / f"{model}.txt"
        found = raw_path.exists() and raw_path.stat().st_size > 50
        bytes_count = raw_path.stat().st_size if raw_path.exists() else 0
        outputs.append({
            "model_account": model,
            "raw_output_path": str(raw_path.relative_to(ROOT_DIR)) if raw_path.exists() else f"model_outputs/raw_rerun/{round_id}/attempt-{attempt_no}/{model}.txt",
            "found": found,
            "bytes": bytes_count,
        })
        if found:
            outputs_found += 1

    outputs_total = len(outputs)
    outputs_missing = outputs_total - outputs_found

    ingested = {
        "version": "p11.1",
        "round_id": round_id,
        "attempt_no": attempt_no,
        "ingested_at": _now_iso(),
        "input_dir": str(input_dir.relative_to(ROOT_DIR)) if input_dir.exists() else args.input_dir,
        "outputs_total": outputs_total,
        "outputs_found": outputs_found,
        "outputs_missing": outputs_missing,
        "outputs": outputs,
    }

    ingested_dir = DATA_DIR / "model_outputs" / "ingested_rerun" / round_id / f"attempt-{attempt_no}"
    ingested_dir.mkdir(parents=True, exist_ok=True)
    _write_json(f"model_outputs/ingested_rerun/{round_id}/attempt-{attempt_no}/index.json", ingested)

    ingested_path = ingested_dir / "index.json"
    print(f"  ✅ Ingested: {outputs_found}/{outputs_total} outputs found")
    print(f"  ✅ Missing: {outputs_missing}")
    print(f"  ✅ Written to: {ingested_path}")
    print()

    if outputs_found > 0:
        print("检测到补跑原始输出。")
        # 未来可在此处串联 rerun-specific pipeline
    else:
        print("未检测到补跑原始输出。")
        print("状态: waiting_for_rerun_outputs")
        print()
        print("请保存模型补跑原始输出到:")
        print(f"  {input_dir}")
        print("然后重新运行 ingest 命令。")


def cmd_status(args):
    """显示补跑状态"""
    round_id = args.round
    verbose = args.verbose

    print("rerun_failed_seats status")
    print(f"round_id: {round_id}")
    print()

    # 检查 rerun_queue
    queue_data = _read_json(f"rerun_queue/{round_id}.json", default=None)
    if queue_data is None:
        print(f"state: no_rerun_queue")
        print(f"next_action: run initial ingest/classify first")
        return

    queue = queue_data.get("queue", [])
    if not queue:
        print(f"state: empty_rerun_queue")
        print(f"next_action: no failed seats to rerun")
        return

    queue_total = len(queue)

    # 检查 attempt ledger
    ledger = _read_json(f"rerun_attempts/{round_id}.json", default=None)
    if ledger is None:
        print(f"queue_total: {queue_total}")
        print(f"state: queue_exists_no_ledger")
        print(f"next_action: run generate-prompts-only first")
        return

    summary = ledger.get("summary", {})
    planned = summary.get("planned_attempts", 0)
    attempts = ledger.get("attempts", [])

    # 推断 attempt_no
    attempt_no = attempts[0].get("attempt_no", 2) if attempts else 2

    # 检查 ingested_rerun
    ingested = _read_json(f"model_outputs/ingested_rerun/{round_id}/attempt-{attempt_no}/index.json", default=None)
    ingested_found = 0
    if ingested:
        ingested_found = ingested.get("outputs_found", 0)

    print(f"queue_total: {queue_total}")
    print(f"planned_attempts: {planned}")
    print(f"attempt_no: {attempt_no}")

    if ingested_found > 0:
        print(f"state: rerun_outputs_ingested")
        print(f"next_action: run rerun validation pipeline (TBD)")
    elif ingested is not None:
        print(f"state: waiting_for_rerun_outputs")
        print(f"next_action: paste rerun outputs into data/pool/model_outputs/raw_rerun/{round_id}/attempt-{attempt_no}/*.txt then run ingest")
    else:
        print(f"state: prompts_generated_waiting_for_outputs")
        raw_dir = DATA_DIR / "model_outputs" / "raw_rerun" / round_id / f"attempt-{attempt_no}"
        print(f"next_action: paste rerun outputs into {raw_dir}/*.txt then run ingest")

    if verbose and attempts:
        print()
        print("=== Attempt Details ===")
        for a in attempts:
            marker = ""
            if a.get("requires_quota_available"):
                marker += " [QUOTA]"
            if a.get("requires_auth_refresh"):
                marker += " [AUTH]"
            print(f"  {a['model_account']}: {a['source_status']} → attempt {a['attempt_no']}/{a['max_attempts']} [{a['state']}]{marker}")


def main():
    parser = argparse.ArgumentParser(description="P11.1 自动补跑机制")
    parser.add_argument("--round", required=True, help="轮次 ID, e.g. run-5")
    parser.add_argument("--max-attempts", type=int, default=3, help="最大补跑次数，默认 3")
    parser.add_argument("--attempt-no", type=int, default=None, help="指定 attempt 编号")
    parser.add_argument("--dry-run", action="store_true", help="Dry run，不写文件")
    parser.add_argument("--generate-prompts-only", action="store_true", help="生成 attempt ledger 和 prompts")
    parser.add_argument("--ingest", action="store_true", help="Ingest 补跑原始输出")
    parser.add_argument("--input-dir", default=None, help="补跑原始输出目录（ingest 必需）")
    parser.add_argument("--status", action="store_true", help="显示补跑状态")
    parser.add_argument("--skip-browser", action="store_true", default=True, help="跳过浏览器")
    parser.add_argument("--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    if args.status:
        cmd_status(args)
    elif args.ingest:
        if not args.input_dir:
            print("ERROR: --ingest requires --input-dir")
            sys.exit(1)
        cmd_ingest(args)
    elif args.generate_prompts_only:
        cmd_generate_prompts(args)
    else:
        # 默认行为：等同于 --dry-run（只显示计划，不写文件）
        if not args.dry_run:
            args.dry_run = True
        cmd_plan(args)


if __name__ == "__main__":
    main()
