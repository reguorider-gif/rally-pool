#!/usr/bin/env python3
"""
ops/classify_model_output.py
P9.3 模型输出状态机分类器

用法:
  python3 ops/classify_model_output.py --round run-5 --dry-run
  python3 ops/classify_model_output.py --round run-5
  python3 ops/classify_model_output.py --round run-6 --dry-run
  python3 ops/classify_model_output.py --round run-5 --input data/pool/archives/run-5.json
  python3 ops/classify_model_output.py --round run-5 --output-dir data/pool --verbose

职责:
  1. 读取指定 round 的模型输出来源
  2. 识别每个模型状态
  3. 写入标准 model_runs
  4. 写入标准 model_outputs
  5. 生成 rerun_queue
  6. 不改写原始档案
  7. 不把失败模型人工修成有效
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------- 项目根目录 ----------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "pool"

# ---------- 13 个模型席位 ----------
MODEL_SEATS = [
    "gemini", "chatgpt", "claude", "yuanbao", "wenxin",
    "deepseek", "mimo", "kimi", "qwen", "xai",
    "minimax", "doubao", "meta",
]

# ---------- 状态判定信号 ----------

PLACEHOLDER_SIGNALS = [
    "你的最终答案", "final answer", "占位", "placeholder", "TODO",
    "待填写", "仅输出最终答案",
]

CONTEXT_POLLUTED_SIGNALS = [
    "狼人杀", "警长", "守卫", "平民", "预言家", "投票淘汰",
    "Grand Judge", "不是当前赛事预测池任务", "旧验收", "AI Judge 狼人杀",
]

QUOTA_BLOCKED_SIGNALS = [
    "quota", "额度不足", "配额", "rate limit", "usage limit",
    "达到上限", "temporarily unavailable",
]

AUTH_BLOCKED_SIGNALS = [
    "login", "auth", "unauthorized", "请登录", "登录失效",
    "token", "session expired",
]

TIMEOUT_SIGNALS = [
    "timeout", "timed out", "超时",
]

RISK_REFUSAL_SIGNALS = [
    "不能下注", "无法提供博彩建议", "不建议投注", "只提供风险审计", "合规原因",
]


# ---------- 状态判定核心 ----------

def _contains_any(text, signals):
    """检查 text 是否包含 signals 中任一关键词（大小写不敏感）"""
    if not text:
        return False
    text_lower = text.lower()
    for s in signals:
        if s.lower() in text_lower:
            return True
    return False


def _find_matched_signals(text, signals):
    """返回 text 中匹配到的信号列表"""
    if not text:
        return []
    text_lower = text.lower()
    matched = []
    for s in signals:
        if s.lower() in text_lower:
            matched.append(s)
    return matched


def classify_model(model_account, record, round_id, verbose=False):
    """
    对单个模型记录进行状态分类。

    输入:
      model_account: 模型账户名
      record: run-5.json 中该模型的 record dict
      round_id: 轮次 ID
      verbose: 是否打印详细过程

    输出: (status_dict, output_dict)
    """
    # 提取可分析文本
    raw_text_parts = []
    for key in ["bets", "thought", "source", "risk", "loan", "stake"]:
        val = record.get(key, "")
        if val and val not in ("not recovered", "0", "placeholder only", "declined betting loan", "No position table or JSON betting receipt."):
            raw_text_parts.append(str(val))

    # 也提取 pollution_signals
    pollution_signals_in_record = record.get("pollution_signals", [])

    raw_text = " ".join(raw_text_parts)

    # 检查原始 status 字段作为辅助线索
    legacy_status = record.get("status", "")

    # 检查 eligible 和 needs_rerun 字段
    eligible = record.get("eligible_for_consensus", None)
    needs_rerun = record.get("needs_rerun", None)

    # 逐步判定
    detected_pollution = _find_matched_signals(raw_text, CONTEXT_POLLUTED_SIGNALS)
    detected_placeholder = _find_matched_signals(raw_text, PLACEHOLDER_SIGNALS)
    detected_quota = _find_matched_signals(raw_text, QUOTA_BLOCKED_SIGNALS)
    detected_auth = _find_matched_signals(raw_text, AUTH_BLOCKED_SIGNALS)
    detected_timeout = _find_matched_signals(raw_text, TIMEOUT_SIGNALS)
    detected_risk_refusal = _find_matched_signals(raw_text, RISK_REFUSAL_SIGNALS)

    # 也检查 record 原有的 pollution_signals
    for ps in pollution_signals_in_record:
        ps_lower = ps.lower()
        if ps_lower in [s.lower() for s in CONTEXT_POLLUTED_SIGNALS]:
            if ps not in detected_pollution:
                detected_pollution.append(ps)
        elif ps_lower in [s.lower() for s in PLACEHOLDER_SIGNALS]:
            if ps not in detected_placeholder:
                detected_placeholder.append(ps)

    # ---------- 状态判定优先级 ----------

    status = "valid_receipt"
    failure_reason = ""
    eligible_for_consensus = True
    needs_rerun_flag = False

    # 1. context_polluted — 最高优先级（污染是严重问题）
    if detected_pollution or "context_polluted" in legacy_status:
        status = "context_polluted"
        failure_reason = "Detected legacy/werewolf context pollution"
        eligible_for_consensus = False
        needs_rerun_flag = True
        if not detected_pollution:
            detected_pollution = _find_matched_signals(
                " ".join(pollution_signals_in_record), CONTEXT_POLLUTED_SIGNALS
            )
            if not detected_pollution:
                detected_pollution = ["werewolf_context"]

    # 2. quota_blocked
    elif detected_quota or "quota_blocked" in legacy_status:
        status = "quota_blocked"
        failure_reason = "Quota/rate limit blocked"
        eligible_for_consensus = False
        needs_rerun_flag = True

    # 3. auth_blocked
    elif detected_auth:
        status = "auth_blocked"
        failure_reason = "Authentication/login required"
        eligible_for_consensus = False
        needs_rerun_flag = True

    # 4. timeout
    elif detected_timeout or (legacy_status == "timeout"):
        status = "timeout"
        failure_reason = "Execution timed out"
        eligible_for_consensus = False
        needs_rerun_flag = True

    # 5. placeholder_only
    elif detected_placeholder or "placeholder" in legacy_status.lower():
        status = "placeholder_only"
        failure_reason = "Output is placeholder only"
        eligible_for_consensus = False
        needs_rerun_flag = True

    # 6. risk_refusal (audit_only_refusal)
    elif detected_risk_refusal or "audit_only" in legacy_status or "refusal" in legacy_status:
        status = "risk_refusal"
        failure_reason = "Risk/compliance refusal — audit only"
        eligible_for_consensus = False
        needs_rerun_flag = False

    # 7. 尝试 JSON 解析
    else:
        # 检查是否有有效回收特征
        is_valid = (
            record.get("eligible_for_consensus") is True
            and record.get("needs_rerun") is False
            and record.get("status", "") in ("valid_recovered", "valid_receipt")
        )

        if is_valid:
            status = "valid_receipt"
            failure_reason = ""
            eligible_for_consensus = True
            needs_rerun_flag = False
        else:
            # 有内容但无法归类的 → parse_error
            if raw_text.strip():
                status = "parse_error"
                failure_reason = "Content present but no valid receipt structure"
                eligible_for_consensus = False
                needs_rerun_flag = True
            else:
                # 无内容 → timeout
                status = "timeout"
                failure_reason = "No content recovered"
                eligible_for_consensus = False
                needs_rerun_flag = True

    # 尊重原始 record 中的 eligible/needs_rerun 字段（如果有显式设置）
    if eligible is not None and not eligible:
        eligible_for_consensus = False
    if needs_rerun is not None and needs_rerun:
        needs_rerun_flag = True

    # 汇总所有检测到的信号
    all_pollution_signals = []
    for sig in detected_pollution:
        all_pollution_signals.append({"signal_type": "context_pollution", "matched_text": sig, "confidence": 0.9})
    for sig in detected_placeholder:
        all_pollution_signals.append({"signal_type": "placeholder_text", "matched_text": sig, "confidence": 0.9})
    for sig in detected_quota:
        all_pollution_signals.append({"signal_type": "quota_blocked", "matched_text": sig, "confidence": 0.9})
    for sig in detected_auth:
        all_pollution_signals.append({"signal_type": "auth_blocked", "matched_text": sig, "confidence": 0.9})
    for sig in detected_risk_refusal:
        all_pollution_signals.append({"signal_type": "risk_refusal", "matched_text": sig, "confidence": 0.8})

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    status_dict = {
        "round_id": round_id,
        "model_account": model_account,
        "seat_id": record.get("seat_id", model_account),
        "attempt_no": 1,
        "status": status,
        "eligible_for_consensus": eligible_for_consensus,
        "needs_rerun": needs_rerun_flag,
        "failure_reason": failure_reason,
        "detected_pollution_signals": detected_pollution if detected_pollution else [],
        "source_path": f"data/pool/archives/{round_id}.json",
        "trace_id": "",
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    output_dict = {
        "round_id": round_id,
        "model_account": model_account,
        "seat_id": record.get("seat_id", model_account),
        "raw_text": raw_text,
        "parsed_json": None,
        "schema_valid": status == "valid_receipt",
        "parse_errors": [] if status == "valid_receipt" else [failure_reason],
        "pollution_signals": all_pollution_signals,
        "source_path": f"data/pool/archives/{round_id}.json",
        "created_at": now_iso,
    }

    if verbose:
        print(f"  {model_account}: {status} (eligible={eligible_for_consensus}, rerun={needs_rerun_flag})")

    return status_dict, output_dict


# ---------- 输入数据适配 ----------

def load_round_data(round_id, input_path=None):
    """
    加载指定 round 的模型输出数据。
    优先从 data/pool/archives/{round_id}.json 读取。
    """
    if input_path:
        path = Path(input_path)
    else:
        path = DATA_DIR / "archives" / f"{round_id}.json"

    if not path.exists():
        print(f"[ERROR] Archive file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def load_model_accounts():
    """加载模型席位列表"""
    path = DATA_DIR / "model_accounts" / "current.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("models", [])
    return []


# ---------- 主流程 ----------

def run_classify(round_id, input_path=None, output_dir=None, dry_run=False, verbose=False):
    """
    执行分类流程。
    """
    if output_dir:
        out_base = Path(output_dir)
    else:
        out_base = DATA_DIR

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 加载数据
    archive_data = load_round_data(round_id, input_path)
    model_records = archive_data.get("model_records", {})

    # 获取完整模型列表（确保 13 个席位都在）
    model_accounts = load_model_accounts()
    model_account_names = [m["model_account"] for m in model_accounts]
    if not model_account_names:
        model_account_names = MODEL_SEATS[:]

    # 合并：确保所有 13 个席位都被处理
    all_models = set(model_account_names) | set(model_records.keys())
    # 保持顺序：先 model_accounts 中的，再 record 中多出来的
    ordered_models = [m for m in model_account_names if m in all_models]
    for m in sorted(all_models - set(ordered_models)):
        ordered_models.append(m)

    # 分类
    runs = []
    outputs = []
    status_counts = {
        "valid_receipt": 0,
        "placeholder_only": 0,
        "context_polluted": 0,
        "quota_blocked": 0,
        "auth_blocked": 0,
        "timeout": 0,
        "parse_error": 0,
        "risk_refusal": 0,
        "needs_rerun": 0,
        "excluded_from_consensus": 0,
    }

    for model_account in ordered_models:
        record = model_records.get(model_account, {
            "status": "pending",
            "loan": "",
            "stake": "",
            "bets": "",
            "thought": "",
            "source": "",
            "risk": "",
            "eligible_for_consensus": None,
            "needs_rerun": None,
        })

        status_dict, output_dict = classify_model(model_account, record, round_id, verbose)

        runs.append(status_dict)
        outputs.append(output_dict)

        # 统计
        s = status_dict["status"]
        if s in status_counts:
            status_counts[s] += 1
        if status_dict["needs_rerun"]:
            status_counts["needs_rerun"] += 1
        if not status_dict["eligible_for_consensus"]:
            status_counts["excluded_from_consensus"] += 1

    total = len(runs)

    # 构建 rerun_queue
    rerun_entry_statuses = {
        "placeholder_only", "context_polluted", "quota_blocked",
        "auth_blocked", "timeout", "parse_error",
    }
    queue = []
    for r in runs:
        if r["status"] in rerun_entry_statuses:
            queue.append({
                "model_account": r["model_account"],
                "seat_id": r["seat_id"],
                "current_status": r["status"],
                "reason": r["failure_reason"],
                "attempt_no": r["attempt_no"],
                "next_attempt_no": r["attempt_no"] + 1,
                "priority": "high" if r["status"] in ("context_polluted", "quota_blocked") else "medium",
            })

    # 构建 model_runs 输出
    model_runs_output = {
        "version": "p9.3",
        "round_id": round_id,
        "generated_at": now_iso,
        "summary": {
            "total": total,
            **status_counts,
        },
        "runs": runs,
    }

    # 构建 model_outputs 输出
    model_outputs_output = {
        "version": "p9.3",
        "round_id": round_id,
        "generated_at": now_iso,
        "outputs": outputs,
    }

    # 构建 rerun_queue 输出
    rerun_queue_output = {
        "version": "p9.3",
        "round_id": round_id,
        "generated_at": now_iso,
        "max_attempts": 3,
        "queue": queue,
    }

    # dry-run 模式：只打印不写文件
    if dry_run:
        print(f"round_id: {round_id}")
        print(f"total: {total}")
        print("status_counts:")
        for k, v in status_counts.items():
            print(f"  {k}: {v}")
        print(f"rerun_queue:")
        for q in queue:
            print(f"  - {q['model_account']}: {q['current_status']} ({q['reason']})")
        print("no files written")
        return

    # 写入文件
    model_runs_dir = out_base / "model_runs"
    model_outputs_dir = out_base / "model_outputs"
    rerun_queue_dir = out_base / "rerun_queue"

    model_runs_dir.mkdir(parents=True, exist_ok=True)
    model_outputs_dir.mkdir(parents=True, exist_ok=True)
    rerun_queue_dir.mkdir(parents=True, exist_ok=True)

    # 创建 raw 子目录（预留，失败不阻塞主流程）
    try:
        (model_outputs_dir / "raw" / round_id).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # 沙箱权限或目录限制，预留目录可稍后手动创建

    mr_path = model_runs_dir / f"{round_id}.json"
    mo_path = model_outputs_dir / f"{round_id}.json"
    rq_path = rerun_queue_dir / f"{round_id}.json"

    with open(mr_path, "w", encoding="utf-8") as f:
        json.dump(model_runs_output, f, ensure_ascii=False, indent=2)
    print(f"Written: {mr_path}")

    with open(mo_path, "w", encoding="utf-8") as f:
        json.dump(model_outputs_output, f, ensure_ascii=False, indent=2)
    print(f"Written: {mo_path}")

    with open(rq_path, "w", encoding="utf-8") as f:
        json.dump(rerun_queue_output, f, ensure_ascii=False, indent=2)
    print(f"Written: {rq_path}")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="P9.3 模型输出状态机分类器")
    parser.add_argument("--round", required=True, help="Round ID, e.g. run-5, run-6")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing files")
    parser.add_argument("--input", default=None, help="Input archive file path (default: data/pool/archives/{round}.json)")
    parser.add_argument("--output-dir", default=None, help="Output base directory (default: data/pool)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    run_classify(
        round_id=args.round,
        input_path=args.input,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
