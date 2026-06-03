#!/usr/bin/env python3
"""
AI Judge 预测池 — 结算脚本
P10.3

用法:
  python3 ops/settle_pool_round.py --round run-5 --date 2026-06-03 --dry-run
  python3 ops/settle_pool_round.py --round run-5 --date 2026-06-03
  python3 ops/settle_pool_round.py --round run-5 --date 2026-06-03 --verbose
  python3 ops/settle_pool_round.py --round run-5 --date 2026-06-03 --force

处理场景:
  - no_bets_to_settle: accepted_bets=0 → 生成无结算文件
  - settled: 正常结算（未来）
  - manual_review: 需人工审核（未来）
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 路径 ───────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "pool"
SETTLE_DIR = DATA_DIR / "settlements"
REPORT_DIR = DATA_DIR / "daily_reports"


def load_json(path, default=None, verbose=False):
    """安全读取 JSON。"""
    p = Path(path)
    if not p.exists():
        if verbose:
            print(f"  [warn] file not found: {p}")
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [error] JSON parse failed: {p}: {e}", file=sys.stderr)
        return default


def settle_round(round_id, date_str, snapshot_label="T-1h",
                 dry_run=False, force=False, verbose=False):
    """执行结算逻辑。"""

    # ── 1. 读取投注单 ─────────────────────────────────────────────────────────
    br_path = DATA_DIR / "bet_receipts" / f"{round_id}.json"
    br_data = load_json(br_path, default=None, verbose=verbose)
    if not br_data:
        print(f"[settle] ERROR: bet receipts not found: {br_path}", file=sys.stderr)
        return None

    summary = br_data.get("summary", {})
    accepted_bets = summary.get("accepted_bets", 0)
    models_total = summary.get("models_total", 0)
    valid_for_settlement = summary.get("valid_for_settlement", False)

    print(f"settle_pool_round")
    print(f"round_id: {round_id}")
    print(f"date: {date_str}")
    print(f"accepted_bets: {accepted_bets}")
    print(f"dry_run: {dry_run}")

    # ── 2. 结算逻辑 ───────────────────────────────────────────────────────────

    if accepted_bets == 0:
        # ── 场景 A: no bets to settle ─────────────────────────────────────────
        settlement_status = "no_bets_to_settle"
        valid_for_lb = False
        settled_bets = 0
        manual_review_bets = 0
        void_bets = 0
        push_bets = 0
        winning_bets = 0
        losing_bets = 0
        total_stake = None
        total_payout = None
        total_profit = None
        roi = None
        settlements = []
        manual_review_list = []
        notes = [{
            "code": "no_accepted_bets",
            "message": "No accepted bets were available for settlement in this round.",
        }]
    elif not valid_for_settlement:
        # ── 场景 B: 有投注但未标记为可结算 ─────────────────────────────────────
        settlement_status = "no_bets_to_settle"
        valid_for_lb = False
        settled_bets = 0
        manual_review_bets = accepted_bets
        void_bets = 0
        push_bets = 0
        winning_bets = 0
        losing_bets = 0
        total_stake = None
        total_payout = None
        total_profit = None
        roi = None
        settlements = []
        manual_review_list = []
        notes = [{
            "code": "not_valid_for_settlement",
            "message": (
                f"Bet receipts have {accepted_bets} accepted bets but "
                "valid_for_settlement=false. Settlement cannot proceed."
            ),
        }]
    else:
        # ── 场景 C: 正常结算（未来实现）────────────────────────────────────────
        # 当前预留结构但不触发
        settlement_status = "manual_review"
        valid_for_lb = False
        settled_bets = 0
        manual_review_bets = accepted_bets
        void_bets = 0
        push_bets = 0
        winning_bets = 0
        losing_bets = 0
        total_stake = None
        total_payout = None
        total_profit = None
        roi = None
        settlements = []
        manual_review_list = []
        notes = [{
            "code": "settlement_not_implemented",
            "message": (
                f"Settlement logic for accepted_bets > 0 is not yet "
                "implemented. All bets moved to manual_review."
            ),
        }]

    print(f"settlement_status: {settlement_status}")

    # ── 3. 构建结算 JSON ─────────────────────────────────────────────────────
    settlement_data = {
        "version": "p10.3",
        "round_id": round_id,
        "date": date_str,
        "snapshot_label": snapshot_label,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settlement_status": settlement_status,
        "valid_for_leaderboard_update": valid_for_lb,
        "summary": {
            "models_total": models_total,
            "accepted_bets": accepted_bets,
            "settled_bets": settled_bets,
            "manual_review_bets": manual_review_bets,
            "void_bets": void_bets,
            "push_bets": push_bets,
            "winning_bets": winning_bets,
            "losing_bets": losing_bets,
            "total_stake": total_stake,
            "total_payout": total_payout,
            "total_profit": total_profit,
            "roi": roi,
        },
        "settlements": settlements,
        "manual_review": manual_review_list,
        "notes": notes,
        "source_files": [
            f"data/pool/bet_receipts/{round_id}.json",
            f"data/pool/bet_receipts/rejections/{round_id}.json",
            f"data/pool/bet_receipts/index.json",
            f"data/pool/match_results/{date_str}.json",
            f"data/pool/odds_snapshots/{date_str}_{snapshot_label}.json",
            f"data/pool/leaderboard/current.json",
            f"data/pool/model_accounts/current.json",
        ],
    }

    if dry_run:
        print("no files written")
        return settlement_data

    # ── 4. 写入 settlements/run-5.json ───────────────────────────────────────
    SETTLE_DIR.mkdir(parents=True, exist_ok=True)
    settle_path = SETTLE_DIR / f"{round_id}.json"
    settle_path.write_text(
        json.dumps(settlement_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if verbose:
        print(f"  [write] {settle_path}")

    # ── 5. 写入/更新 settlements/index.json ──────────────────────────────────
    idx_path = SETTLE_DIR / "index.json"
    existing_idx = load_json(idx_path, default={"version": "p10.3", "updated_at": "", "rounds": []})
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing_rounds = existing_idx.get("rounds", [])
    # 删除同 round_id 的旧记录
    existing_rounds = [r for r in existing_rounds if r.get("round_id") != round_id]
    existing_rounds.append({
        "round_id": round_id,
        "date": date_str,
        "path": f"data/pool/settlements/{round_id}.json",
        "settlement_status": settlement_status,
        "accepted_bets": accepted_bets,
        "settled_bets": settled_bets,
        "valid_for_leaderboard_update": valid_for_lb,
        "roi": roi,
    })
    index_data = {
        "version": "p10.3",
        "updated_at": now_ts,
        "rounds": existing_rounds,
    }
    idx_path.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if verbose:
        print(f"  [write] {idx_path}")

    # ── 6. 生成 Markdown 结算报告 ────────────────────────────────────────────
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORT_DIR / f"settlement_{round_id}.md"
    md_content = generate_markdown_report(settlement_data, br_data, round_id, date_str)
    md_path.write_text(md_content, encoding="utf-8")
    if verbose:
        print(f"  [write] {md_path}")

    print(f"  ✓ settlements/{round_id}.json written")
    print(f"  ✓ settlements/index.json updated")
    print(f"  ✓ daily_reports/settlement_{round_id}.md written")

    return settlement_data


def generate_markdown_report(settlement_data, br_data, round_id, date_str):
    """生成 settlement Markdown 报告。"""
    s = settlement_data["summary"]
    notes_text = "\n".join(
        f"- **{n['code']}**: {n['message']}" for n in settlement_data.get("notes", [])
    )
    source_text = "\n".join(
        f"- `{sf}`" for sf in settlement_data.get("source_files", [])
    )

    # Rejection summary
    rj_path = DATA_DIR / "bet_receipts" / "rejections" / f"{round_id}.json"
    rj_data = load_json(rj_path, default=None)
    rj_summary = "N/A"
    if rj_data:
        rc = rj_data.get("rejection_summary", {})
        rc_text = rc.get("reason_counts", {})
        rj_summary = f"{rj_data.get('total_rejected', '?')} rejections"
        if rc_text:
            detail_lines = "\n".join(f"  - {k}: {v}" for k, v in sorted(rc_text.items()))
            rj_summary += f"\n{detail_lines}"

    return f"""# AI Judge 赛事预测池结算报告 — {round_id}

## 1. 结算结论

本轮 **accepted_bets=0**，因此没有可结算投注。

- **settlement_status**: `{settlement_data["settlement_status"]}`
- **valid_for_leaderboard_update**: `{settlement_data["valid_for_leaderboard_update"]}`
- **profit/ROI 不应计算为 0**，而应标记为 null / not_applicable。

## 2. Bet Receipt 摘要

- **models_total**: {s["models_total"]}
- **accepted_bets**: {s["accepted_bets"]}
- **rejected_bets**: {br_data.get("summary", {}).get("rejected_bets", "N/A")}
- **valid_for_settlement**: {br_data.get("summary", {}).get("valid_for_settlement", "N/A")}

## 3. Rejection 摘要

{rj_summary}

## 4. 结算结果

| 项目 | 值 |
|---|---|
| settlement_status | {settlement_data["settlement_status"]} |
| accepted_bets | {s["accepted_bets"]} |
| settled_bets | {s["settled_bets"]} |
| total_profit | {s["total_profit"]} |
| roi | {s["roi"]} |
| valid_for_leaderboard_update | {settlement_data["valid_for_leaderboard_update"]} |
| winning_bets | {s["winning_bets"]} |
| losing_bets | {s["losing_bets"]} |
| void_bets | {s["void_bets"]} |
| push_bets | {s["push_bets"]} |
| manual_review_bets | {s["manual_review_bets"]} |

## 5. 为什么没有 ROI

本轮 accepted_bets=0，因此没有可结算投注。

profit 和 ROI 不应计算为 0，而应标记为 **null** / **not_applicable**。

原因：没有下注 → 0 收益不等于结算为 0。标记为 null 可防止后续排行榜误解读。

## 6. 下一步动作

{notes_text}

- 等待补跑完成后，重新运行 validate_model_outputs.py 生成有 structured receipts 的投注单。
- 配置真实赔率源（the_odds_api），使 odds snapshots 有有效赔率行。
- 重新运行 settle_pool_round.py 进行真实结算。

## 7. 来源文件

{source_text}

---
*生成时间: {settlement_data["generated_at"]}*
*版本: {settlement_data["version"]}*
"""


def main():
    parser = argparse.ArgumentParser(
        description="AI Judge 预测池 — 结算脚本 (P10.3)",
    )
    parser.add_argument("--round", required=True, help="round_id, e.g. run-5")
    parser.add_argument("--date", required=True, help="date, e.g. 2026-06-03")
    parser.add_argument("--snapshot-label", default="T-1h",
                        help="odds snapshot label (default: T-1h)")
    parser.add_argument("--dry-run", action="store_true",
                        help="dry-run: do not write files")
    parser.add_argument("--force", action="store_true",
                        help="force overwrite existing settlement")
    parser.add_argument("--verbose", action="store_true",
                        help="verbose output")
    args = parser.parse_args()

    settle_round(
        round_id=args.round,
        date_str=args.date,
        snapshot_label=args.snapshot_label,
        dry_run=args.dry_run,
        force=args.force,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
