#!/usr/bin/env python3
"""
AI Judge 预测池 — 每日自动报告生成脚本
P9.4

用法:
  python3 ops/generate_daily_pool_report.py --date 2026-06-03 --round run-5
  python3 ops/generate_daily_pool_report.py --date 2026-06-03 --round run-5 --dry-run
  python3 ops/generate_daily_pool_report.py --date 2026-06-03 --round run-5 --verbose
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 路径 ───────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "pool"
REPORT_DIR = DATA_DIR / "daily_reports"

# ── 输入文件 ──────────────────────────────────────────────────────────────────
REQUIRED_FILES = {
    "matches":       DATA_DIR / "matches" / "current.json",
    "model_accounts": DATA_DIR / "model_accounts" / "current.json",
    "leaderboard":    DATA_DIR / "leaderboard" / "current.json",
    "archives_index": DATA_DIR / "archives" / "index.json",
    "archive_run5":  DATA_DIR / "archives" / "run-5.json",
    "model_runs":    DATA_DIR / "model_runs" / "run-5.json",
    "model_outputs":  DATA_DIR / "model_outputs" / "run-5.json",
    "rerun_queue":   DATA_DIR / "rerun_queue" / "run-5.json",
    "frontend_archives": DATA_DIR / "app_static" / "frontend_archives.json",
}

OPTIONAL_FILES = {
    "odds_snapshots":  list((DATA_DIR / "odds_snapshots").glob("*.json")) if (DATA_DIR / "odds_snapshots").exists() else [],
    "settlements":     DATA_DIR / "settlements" / "run-5.json",
    "match_results":   list((DATA_DIR / "match_results").glob("*.json")) if (DATA_DIR / "match_results").exists() else [],
}

# ── 状态枚举 ──────────────────────────────────────────────────────────────────
ALL_STATUSES = [
    "valid_receipt", "placeholder_only", "context_polluted",
    "quota_blocked", "auth_blocked", "timeout",
    "parse_error", "risk_refusal", "excluded_from_consensus",
]

CONSENSUS_ELIGIBLE = {"valid_receipt"}


# ── 工具函数 ──────────────────────────────────────────────────────────────────
def load_json(path: Path, default=None, verbose=False):
    """安全读取 JSON，不存在返回 default。"""
    if default is None:
        default = {}
    if not path.exists():
        if verbose:
            print(f"  [skip] file not found: {path}")
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        if verbose:
            print(f"  [error] failed to parse {path}: {e}")
        return default


def count_by_status(runs_data: dict) -> dict:
    """从 model_runs 统计各状态数量。"""
    counts = {s: 0 for s in ALL_STATUSES}
    runs = runs_data.get("runs", [])
    for r in runs:
        st = r.get("status", "")
        if st in counts:
            counts[st] += 1
    # 也尝试从 summary 读取
    summary = runs_data.get("summary", {})
    if summary:
        for s in ALL_STATUSES:
            if s in summary:
                counts[s] = summary[s]
    return counts


def build_model_status_rows(runs_data: dict) -> list:
    """构建 model_status_rows（用于 JSON 报告和 Markdown 表格）。"""
    rows = []
    for r in runs_data.get("runs", []):
        rows.append({
            "model_account":  r.get("model_account", ""),
            "seat_id":        r.get("seat_id", ""),
            "status":         r.get("status", ""),
            "eligible_for_consensus": r.get("eligible_for_consensus", False),
            "needs_rerun":    r.get("needs_rerun", False),
            "failure_reason": r.get("failure_reason", ""),
            "pollution_signals": r.get("detected_pollution_signals", []),
        })
    return rows


def detect_data_gaps(required_data: dict, optional_data: dict) -> list:
    """检测数据缺口。"""
    gaps = []
    # 必需文件缺失（已在调用处处理，这里检测内容缺口）
    # 可选文件缺失 → data_gaps
    # 赔率快照三态检测（P10.1）
    odds_snap_paths = optional_data.get("odds_snapshots", [])
    if not odds_snap_paths:
        gaps.append({
            "gap": "missing_odds_snapshots",
            "severity": "medium",
            "blocking": False,
            "stage": "P10.1",
            "detail": "No odds snapshot files found for report date.",
        })
    else:
        # odds_snap_paths 是字符串列表，转为 Path 后取最新
        snap_paths = [Path(p) for p in odds_snap_paths]
        latest_snap_path = max(snap_paths, key=lambda p: p.stat().st_mtime) if snap_paths else None
        valid_odds_rows = 0
        if latest_snap_path:
            snap = load_json(latest_snap_path, default={}, verbose=False)
            summary = snap.get("summary", {})
            # 优先用 summary.valid_odds_rows
            valid_odds_rows = summary.get("valid_odds_rows")
            if valid_odds_rows is None:
                # 回退：逐行计算
                odds_rows = snap.get("odds", [])
                valid_odds_rows = 0
                for row in odds_rows:
                    odds_val = row.get("odds")
                    status = row.get("status", "")
                    if (isinstance(odds_val, (int, float)) and odds_val > 1
                            and status not in ("missing_market_coverage",
                                               "provider_unavailable",
                                               "match_mapping_failed",
                                               "manual_review")):
                        valid_odds_rows += 1

        if valid_odds_rows <= 0:
            gaps.append({
                "gap": "odds_snapshots_present_but_missing_market_coverage",
                "severity": "medium",
                "blocking": False,
                "stage": "P10.1",
                "detail": "Odds snapshot exists, but no valid odds rows available. Provider may be manual_stub or missing market coverage.",
            })
        else:
            gaps.append({
                "gap": "odds_snapshots_present",
                "severity": "info",
                "blocking": False,
                "stage": "P10.1",
                "detail": f"Odds snapshot exists with {valid_odds_rows} valid odds rows.",
            })
    if not optional_data.get("settlements"):
        gaps.append({
            "gap": "missing_settlements",
            "severity": "high",
            "blocks": "P10.3 settlement",
            "note": "data/pool/settlements/run-5.json not found",
        })
    if not optional_data.get("match_results"):
        gaps.append({
            "gap": "missing_match_results",
            "severity": "medium",
            "blocks": "P10.2 result syncing",
            "note": "No match result files in data/pool/match_results/",
        })
    else:
        # P10.0: 检查 match_results 是否存在但全是未完成
        mr_data = optional_data.get("match_results", {})
        mr_summary = mr_data.get("summary", {})
        mr_total = mr_summary.get("total", 0)
        mr_finished = mr_summary.get("finished", 0)
        if mr_total > 0 and mr_finished == 0:
            gaps.append({
                "gap": "match_results_present_but_unfinished",
                "severity": "info",
                "blocks": "P10.2 result fetching from external source",
                "note": f"Match results file exists ({mr_total} matches) but all are unfinished/missing — no external result source yet",
            })
    # 检查 pipeline_runs 目录
    pipeline_dir = DATA_DIR / "pipeline_runs"
    if not pipeline_dir.exists() or not list(pipeline_dir.glob("*.json")):
        gaps.append({
            "gap": "missing_daily_pipeline",
            "severity": "low",
            "blocks": "P12.0 pipeline orchestration",
            "note": "No pipeline run records found",
        })
    # 检查 bet_receipts — P10.2 四态检测
    bet_br_path = DATA_DIR / "bet_receipts" / "run-5.json"
    if not bet_br_path.exists():
        gaps.append({
            "gap": "missing_bet_receipts",
            "severity": "high",
            "blocks": "P10.3 settlement, risk summary",
            "note": "No bet receipt files in data/pool/bet_receipts/",
        })
    else:
        br = load_json(bet_br_path, default=None, verbose=False)
        if br:
            summary = br.get("summary", {})
            accepted = summary.get("accepted_bets", 0)
            vfs = summary.get("valid_for_settlement", False)
            if accepted == 0:
                gaps.append({
                    "gap": "bet_receipts_present_but_no_valid_bets",
                    "severity": "high",
                    "blocking": True,
                    "stage": "P10.2",
                    "detail": "Bet receipts exist but 0 accepted bets. Models lack structured receipts or odds coverage is missing.",
                })
            elif not vfs:
                gaps.append({
                    "gap": "bet_receipts_present_but_not_settleable",
                    "severity": "medium",
                    "blocking": True,
                    "stage": "P10.3",
                    "detail": f"Bet receipts have {accepted} accepted bets but valid_for_settlement=false.",
                })
            else:
                gaps.append({
                    "gap": "bet_receipts_present_and_settleable",
                    "severity": "info",
                    "blocking": False,
                    "stage": "P10.3",
                    "detail": f"Bet receipts ready with {accepted} accepted bets.",
                })
    return gaps


def generate_next_actions(rerun_queue: list, data_gaps: list) -> list:
    """根据数据自动生成 next_actions。"""
    actions = []
    # 1. 补跑队列不为空
    if rerun_queue:
        actions.append({
            "action": "rerun_failed_seats",
            "reason": f"Rerun queue has {len(rerun_queue)} models to retry",
            "stage": "P11.1",
            "blocking": False,
        })
    # 2. 赔率快照三态
    has_odds_gap = any(g.get("gap") == "missing_odds_snapshots" for g in data_gaps)
    has_odds_coverage_gap = any(g.get("gap") == "odds_snapshots_present_but_missing_market_coverage" for g in data_gaps)
    has_odds_present = any(g.get("gap") == "odds_snapshots_present" for g in data_gaps)
    if has_odds_gap:
        actions.append({
            "action": "sync_odds_snapshots",
            "reason": "Odds snapshots missing; needed for consensus and settlement",
            "stage": "P10.1",
            "blocking": False,
        })
    elif has_odds_coverage_gap:
        actions.append({
            "action": "sync_odds_snapshots_with_real_provider",
            "reason": "Odds snapshots exist but no valid odds rows — configure the_odds_api or another real provider",
            "stage": "P10.1",
            "blocking": False,
        })
    # 3. 赛果缺失或未完成
    if any(g["gap"] == "missing_match_results" for g in data_gaps):
        actions.append({
            "action": "sync_results",
            "reason": "Match results missing; needed for settlement",
            "stage": "P10.2",
            "blocking": False,
        })
    if any(g["gap"] == "match_results_present_but_unfinished" for g in data_gaps):
        actions.append({
            "action": "fetch_external_results",
            "reason": "Match results file exists but all matches are unfinished — need external data source",
            "stage": "P10.2",
            "blocking": False,
        })
    # 4. 结算缺失
    if any(g["gap"] == "missing_settlements" for g in data_gaps):
        actions.append({
            "action": "settle_pool_round",
            "reason": "Settlements missing; needed for ROI and leaderboard update",
            "stage": "P10.3",
            "blocking": False,
        })
    # 5. 报告已生成（本脚本生成后）
    actions.append({
        "action": "publish_or_deploy_report",
        "reason": "Daily report generated; consider publishing to frontend or Vercel",
        "stage": "P9.4",
        "blocking": False,
    })
    return actions


def build_consensus_eligibility(runs_data: dict) -> dict:
    """计算共识准入情况。"""
    eligible = []
    excluded = []
    for r in runs_data.get("runs", []):
        ma = r.get("model_account", "")
        if r.get("eligible_for_consensus") and r.get("status") in CONSENSUS_ELIGIBLE:
            eligible.append(ma)
        else:
            excluded.append({
                "model_account": ma,
                "status": r.get("status", ""),
                "reason": r.get("failure_reason", "Not eligible for consensus"),
            })
    return {
        "eligible_count":   len(eligible),
        "eligible_models":  eligible,
        "excluded_count":   len(excluded),
        "excluded_models":  excluded,
    }


def build_risk_summary(model_outputs_data: dict, bet_receipts_exist: bool,
                       settlements_exist: bool) -> dict:
    """构建风险摘要。当前无投注单/结算数据，标记 missing。"""
    if not bet_receipts_exist or not settlements_exist:
        return {
            "total_stake":      None,
            "max_single_match_risk": None,
            "loan_used":        None,
            "status":           "missing_bet_receipts_or_settlements",
            "note":             "Cannot compute risk without bet_receipts and settlements",
        }
    # 未来：从 bet_receipts 和 settlements 计算实际风险
    return {
        "total_stake":      None,
        "max_single_match_risk": None,
        "loan_used":        None,
        "status":           "not_implemented",
    }


# ── 报告生成 ──────────────────────────────────────────────────────────────────
def generate_json_report(date_str: str, round_id: str,
                        required_data: dict, optional_data: dict,
                        verbose: bool = False) -> dict:
    """生成 JSON 报告字典。"""
    runs_data      = required_data.get("model_runs", {})
    rerun_data      = required_data.get("rerun_queue", {})
    outputs_data    = required_data.get("model_outputs", {})

    # 状态统计
    model_status_counts = count_by_status(runs_data)
    model_status_rows   = build_model_status_rows(runs_data)

    # 总模型数 & 比赛数
    total_models  = runs_data.get("summary", {}).get("total", len(model_status_rows))
    matches_data  = required_data.get("matches", {})
    total_matches = matches_data.get("total", len(matches_data.get("matches", [])))

    # 补跑队列
    rerun_queue_list = rerun_data.get("queue", [])

    # 数据缺口
    bet_receipts_exist  = bool(optional_data.get("bet_receipts", []))
    settlements_exist   = bool(optional_data.get("settlements"))
    data_gaps = detect_data_gaps(required_data, optional_data)

    # 共识准入
    consensus = build_consensus_eligibility(runs_data)

    # 风险摘要
    risk = build_risk_summary(outputs_data, bet_receipts_exist, settlements_exist)

    # 下一步动作
    next_actions = generate_next_actions(rerun_queue_list, data_gaps)

    # 来源文件列表
    source_files = [
        str(p) for p in REQUIRED_FILES.values()
        if isinstance(p, Path) and p.exists()
    ]
    for key, val in optional_data.items():
        if isinstance(val, list):
            for f in val:
                source_files.append(str(f))
        elif isinstance(val, Path) and val.exists():
            source_files.append(str(val))

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 标题 — 从 runs 中直接计算 needs_rerun
    needs_rerun_count = sum(1 for r in runs_data.get("runs", []) if r.get("needs_rerun"))
    valid      = model_status_counts.get("valid_receipt", 0)
    headline   = (f"Run #5 Daily Report — {valid} valid outputs, "
                  f"{needs_rerun_count} models need rerun, {len(data_gaps)} data gaps")

    report = {
        "version":  "p9.4",
        "date":     date_str,
        "round_id": round_id,
        "generated_at": now_iso,
        "summary": {
            "headline":         headline,
            "status":           "report_generated",
            "total_models":     total_models,
            "total_matches":    total_matches,
            "rerun_queue_count": len(rerun_queue_list),
        },
        "model_status_counts": model_status_counts,
        "model_status_rows":   model_status_rows,
        "rerun_queue":        rerun_queue_list,
        "consensus_eligibility": consensus,
        "risk_summary":       risk,
        "data_gaps":          data_gaps,
        "next_actions":       next_actions,
        "generated_files":    [],   # 由调用方填充
        "source_files":       source_files,
    }
    return report


def generate_markdown_report(json_report: dict) -> str:
    """将 JSON 报告转换为 Markdown 字符串。"""
    lines = []
    s   = json_report["summary"]
    msc = json_report["model_status_counts"]
    rows = json_report.get("model_status_rows", [])
    rq  = json_report.get("rerun_queue", [])
    c   = json_report.get("consensus_eligibility", {})
    r   = json_report.get("risk_summary", {})
    dg  = json_report.get("data_gaps", [])
    na  = json_report.get("next_actions", [])

    # 1. 总览
    lines.append(f"# AI Judge 赛事预测池日报 — {json_report['date']} / {json_report['round_id']}")
    lines.append("")
    lines.append("## 1. 总览")
    lines.append("")
    lines.append(f"- **报告版本**: {json_report['version']}")
    lines.append(f"- **生成时间**: {json_report['generated_at']}")
    lines.append(f"- **总模型数**: {s['total_models']}")
    lines.append(f"- **总比赛数**: {s['total_matches']}")
    lines.append(f"- **补跑队列数量**: {s['rerun_queue_count']}")
    lines.append(f"- **数据缺口数**: {len(dg)}")
    lines.append(f"- **下一步动作数**: {len(na)}")
    lines.append("")

    # 2. 模型状态统计
    lines.append("## 2. 模型状态统计")
    lines.append("")
    lines.append("| 状态 | 数量 | 模型 |")
    lines.append("|------|------|------|")
    status_display = {
        "valid_receipt":     "✅ valid_receipt（有效输出）",
        "placeholder_only":   "🟡 placeholder_only（占位文本）",
        "context_polluted":   "🔴 context_polluted（上下文污染）",
        "quota_blocked":      "🟠 quota_blocked（配额阻塞）",
        "risk_refusal":       "🟣 risk_refusal（合规拒绝）",
        "auth_blocked":      "⚫ auth_blocked",
        "timeout":           "⚫ timeout",
        "parse_error":        "⚫ parse_error",
        "excluded_from_consensus": "⚫ excluded_from_consensus",
    }
    for st, label in status_display.items():
        cnt = msc.get(st, 0)
        if cnt == 0:
            continue
        names = [r["model_account"] for r in rows if r["status"] == st]
        lines.append(f"| {label} | {cnt} | {', '.join(names)} |")
    lines.append("")

    # 3. 需要补跑的模型
    lines.append("## 3. 需要补跑的模型")
    lines.append("")
    if rq:
        lines.append("| 模型 | 当前状态 | 原因 | 下次尝试 | 优先级 |")
        lines.append("|------|----------|------|----------|--------|")
        for item in rq:
            lines.append(
                f"| {item.get('model_account','')} "
                f"| {item.get('current_status','')} "
                f"| {item.get('reason','')} "
                f"| #{item.get('next_attempt_no','?')} "
                f"| {item.get('priority','normal')} |")
    else:
        lines.append("（补跑队列为空）")
    lines.append("")

    # 4. 有效输出与共识准入
    lines.append("## 4. 有效输出与共识准入")
    lines.append("")
    lines.append(f"- **可进入共识模型数**: {c.get('eligible_count', 0)}")
    lines.append(f"- **可进入共识模型**: {', '.join(c.get('eligible_models', [])) or '（无）'}")
    lines.append(f"- **被排除模型数**: {c.get('excluded_count', 0)}")
    lines.append("")
    lines.append("**排除原因：**")
    for ex in c.get("excluded_models", []):
        lines.append(f"- {ex['model_account']}: `{ex['status']}` — {ex['reason']}")
    lines.append("")

    # 5. 数据缺口
    lines.append("## 5. 数据缺口")
    lines.append("")
    if dg:
        lines.append("| 缺口 | 严重程度 | 阻塞阶段 | 说明 |")
        lines.append("|------|----------|----------|------|")
        for g in dg:
            lines.append(f"| `{g.get('gap', '')}` | {g.get('severity', '')} | {g.get('blocking', g.get('blocks', ''))} | {g.get('detail', g.get('note', ''))} |")
    else:
        lines.append("（无数据缺口）")
    lines.append("")
    lines.append(f"**是否可以计算 ROI**: 否（原因：缺少投注单/结算/赔率快照）")
    lines.append(f"**赔率数据**: {'缺失' if any(g['gap']=='missing_odds_snapshots' for g in dg) else '存在'}")  
    lines.append(f"**结算数据**: {'缺失' if any(g['gap']=='missing_settlements' for g in dg) else '存在'}")  
    lines.append(f"**赛果数据**: {'缺失' if any(g['gap']=='missing_match_results' for g in dg) else '存在'}")  
    lines.append("")

    # 6. 风险摘要
    lines.append("## 6. 风险摘要")
    lines.append("")
    lines.append(f"- **状态**: `{r.get('status', 'unknown')}`")
    if r.get("total_stake") is not None:
        lines.append(f"- **总投注额**: {r['total_stake']}")
        lines.append(f"- **单场最大风险**: {r['max_single_match_risk']}")
        lines.append(f"- **借贷已用**: {r['loan_used']}")
    else:
        lines.append(f"- **总投注额**: 无法计算（缺少投注单）")
        lines.append(f"- **单场最大风险**: 无法计算（缺少投注单）")
        lines.append(f"- **借贷已用**: 无法计算（缺少投注单）")
    lines.append(f"- **说明**: {r.get('note', '')}")
    lines.append("")

    # 7. 下一步动作
    lines.append("## 7. 下一步动作")
    lines.append("")
    for i, a in enumerate(na, 1):
        lines.append(f"{i}. **`{a['action']}`** — {a['reason']}（阶段: {a['stage']}）")
    lines.append("")

    # 8. 来源文件
    lines.append("## 8. 来源文件")
    lines.append("")
    for f in json_report.get("source_files", []):
        lines.append(f"- `{f}`")
    lines.append("")

    return "\n".join(lines)


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AI Judge 预测池每日报告生成脚本 (P9.4)")
    parser.add_argument("--date",   required=True, help="报告日期，格式 YYYY-MM-DD")
    parser.add_argument("--round",  required=True, help="轮次 ID，如 run-5")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    parser.add_argument("--verbose", action="store_true", help="打印调试信息")
    args = parser.parse_args()

    date_str  = args.date
    round_id  = args.round
    dry_run   = args.dry_run
    verbose   = args.verbose

    if verbose:
        print(f"[P9.4] Generating daily report: date={date_str}, round={round_id}, dry_run={dry_run}")

    # ── 读取必需文件 ──────────────────────────────────────────────────────────
    required_data = {}
    for key, path in REQUIRED_FILES.items():
        data = load_json(path, default={}, verbose=verbose)
        required_data[key] = data
        if not data and verbose:
            print(f"  [warn] required data empty: {key} ({path})")

    # ── 读取可选文件 ──────────────────────────────────────────────────────────
    optional_data = {}
    # odds_snapshots: 已在 REQUIRED_FILES 外处理为 list
    odds_dir = DATA_DIR / "odds_snapshots"
    optional_data["odds_snapshots"] = (
        [str(p) for p in odds_dir.glob("*.json")] if odds_dir.exists() else []
    )
    # settlements
    settle_path = DATA_DIR / "settlements" / f"{round_id}.json"
    optional_data["settlements"] = load_json(settle_path, default=None, verbose=verbose)
    optional_data["settlements_path"] = settle_path
    # match_results — P10.0: load the actual file for the date
    mr_path = DATA_DIR / "match_results" / f"{date_str}.json"
    optional_data["match_results"] = load_json(mr_path, default=None, verbose=verbose)
    optional_data["match_results_path"] = mr_path
    # bet_receipts
    br_dir = DATA_DIR / "bet_receipts"
    optional_data["bet_receipts"] = (
        [str(p) for p in br_dir.glob("*.json")] if br_dir.exists() else []
    )

    # ── 生成 JSON 报告 ────────────────────────────────────────────────────────
    json_report = generate_json_report(date_str, round_id,
                                       required_data, optional_data, verbose)

    # ── 生成 Markdown 报告 ────────────────────────────────────────────────────
    md_content = generate_markdown_report(json_report)

    # ── dry-run 输出 ──────────────────────────────────────────────────────────
    s   = json_report["summary"]
    msc = json_report["model_status_counts"]
    if dry_run:
        needs_rerun_count = sum(1 for r in required_data.get("model_runs", {}).get("runs", []) if r.get("needs_rerun"))
        print(f"report_date:       {date_str}")
        print(f"round_id:          {round_id}")
        print(f"total_models:      {s['total_models']}")
        print(f"total_matches:     {s['total_matches']}")
        print(f"rerun_queue_count: {s['rerun_queue_count']}")
        print(f"data_gaps_count:   {len(json_report['data_gaps'])}")
        print(f"valid_receipt:     {msc.get('valid_receipt', 0)}")
        print(f"needs_rerun:       {needs_rerun_count}")
        print(f"dry_run:           true")
        print(f"no files written")
        # 数据缺口
        if json_report["data_gaps"]:
            print("\ndata_gaps:")
            for g in json_report["data_gaps"]:
                print(f"  - {g['gap']} ({g['severity']}): {g['note']}")
        # 下一步动作
        if json_report["next_actions"]:
            print("\nnext_actions:")
            for a in json_report["next_actions"]:
                print(f"  - {a['action']}: {a['reason']}")
        return

    # ── 正式写入文件 ──────────────────────────────────────────────────────────
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORT_DIR / f"{date_str}_{round_id}.json"
    md_path   = REPORT_DIR / f"{date_str}_{round_id}.md"

    # 写入 JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)
    if verbose:
        print(f"  [write] {json_path}")

    # 写入 Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    if verbose:
        print(f"  [write] {md_path}")

    # 更新 generated_files
    json_report["generated_files"] = [str(json_path), str(md_path)]

    # 完成输出
    print(f"✅ Report generated:")
    print(f"   JSON: {json_path}")
    print(f"   MD:   {md_path}")
    print(f"   total_models:      {s['total_models']}")
    print(f"   valid_receipt:     {msc.get('valid_receipt', 0)}")
    print(f"   rerun_queue_count: {s['rerun_queue_count']}")
    print(f"   data_gaps:         {len(json_report['data_gaps'])}")


if __name__ == "__main__":
    main()
