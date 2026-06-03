#!/usr/bin/env python3
"""
ops/check_pool_data_health.py
P9.3 增强数据健康检查脚本

检查 data/pool/ 下关键文件的存在性、JSON 语法、记录数。
同时检查 HTML 硬编码残留、app.py 路由、P9.3 状态机数据完整性。

退出码：
  hard fail → 非 0
  warning only → 0 但打印 warning
"""

from pathlib import Path
import json
import sys
import re

# 定位项目根目录
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "pool"
DOCS_DIR = ROOT / "docs"
OPS_DIR = ROOT / "ops"
HTML_FILE = ROOT / "html" / "index.html"
APP_FILE = ROOT / "app.py"


def check_file(relative_path, expect_count_fn=None, warn_on_count=None):
    """检查单个文件：存在性 + JSON 解析 + 记录数"""
    full = DATA / relative_path
    result = {
        "path": f"data/pool/{relative_path}",
        "exists": False,
        "valid_json": False,
        "record_count": 0,
        "warning": "",
    }
    if not full.exists():
        result["warning"] = "file not found"
        return result

    result["exists"] = True
    try:
        with open(full, "r", encoding="utf-8") as f:
            data = json.load(f)
        result["valid_json"] = True
    except json.JSONDecodeError as e:
        result["warning"] = f"JSON parse error: {e}"
        return result
    except Exception as e:
        result["warning"] = f"read error: {e}"
        return result

    # 计算记录数
    if expect_count_fn:
        try:
            result["record_count"] = expect_count_fn(data)
        except Exception:
            result["record_count"] = 0
            result["warning"] = (result.get("warning") or "") + " | count function failed"

    # 检查预期记录数
    if warn_on_count is not None:
        if result["record_count"] != warn_on_count:
            result["warning"] = (
                (result.get("warning") or "")
                + f" | expected {warn_on_count} records, got {result['record_count']}"
            )

    return result


def main():
    print("=== P9.3 Data Health Check ===")
    print(f"DATA DIR: {DATA}")
    print()

    has_error = False
    has_warning = False
    results = []

    # --- 关键文件检查 ---
    checks = [
        ("model_accounts/current.json", lambda d: len(d.get("models", [])), 13, True, True),
        ("leaderboard/current.json", lambda d: len(d.get("leaderboard", [])), 13, True, True),
        ("matches/current.json", lambda d: len(d.get("matches", [])), 21, True, True),
        ("archives/index.json", lambda d: len(d.get("rounds", [])), 2, True, False),
        ("archives/run-4.json", lambda d: 1, 1, True, False),
        ("archives/run-5.json", lambda d: 1, 1, True, False),
        ("app_static/frontend_archives.json", lambda d: 1, 1, True, False),
        # P9.3 新增
        ("model_runs/run-5.json", lambda d: d.get("summary", {}).get("total", 0), 13, True, True),
        ("model_outputs/run-5.json", lambda d: len(d.get("outputs", [])), 13, True, True),
        ("rerun_queue/run-5.json", lambda d: len(d.get("queue", [])), None, True, False),
    ]

    for rel_path, count_fn, expected, required, hard_fail_count in checks:
        r = check_file(rel_path, count_fn, expected)
        results.append(r)
        status = "✅" if r["valid_json"] else "❌"
        count_ok = r["record_count"] == expected
        count_icon = "✅" if count_ok else ("❌" if hard_fail_count else "⚠️")
        print(f"  {status} {r['path']}  (records: {r['record_count']} {count_icon})")
        if r["warning"]:
            print(f"       ⚠️  {r['warning']}")
            if "JSON parse error" in r["warning"]:
                has_error = True
        if required and not r["exists"]:
            has_error = True
        if hard_fail_count and r["exists"] and r["valid_json"] and not count_ok:
            print(f"       ❌ HARD FAIL: expected {expected} records, got {r['record_count']}")
            has_error = True

    # --- frontend_archives.json 子检查 ---
    fa_path = DATA / "app_static" / "frontend_archives.json"
    if fa_path.exists():
        try:
            fa = json.loads(fa_path.read_text(encoding="utf-8"))
            print("\n=== frontend_archives.json 子字段检查 ===")
            for k, expected_len in [
                ("round_results", 6),
                ("run4_model_archive", 13),
                ("run5_model_archive", 13),
                ("run4_source_tasks", 4),
                ("ucl_bets", 13),
            ]:
                v = fa.get(k, [])
                actual = len(v) if isinstance(v, list) else -1
                icon = "✅" if actual == expected_len else "⚠️"
                print(f"  {icon} {k}: {actual} (expected {expected_len})")
                if actual == -1:
                    print(f"       ⚠️ {k} is not a list")
                    has_warning = True
        except Exception as e:
            print(f"[WARN] Failed to check frontend_archives.json sub-fields: {e}")

    print()

    # --- Run #5 状态检查：污染/占位/阻塞不得丢失 ---
    run5_path = DATA / "archives" / "run-5.json"
    if run5_path.exists():
        try:
            with open(run5_path, "r", encoding="utf-8") as f:
                run5 = json.load(f)
            models = run5.get("model_records", {})
            print("=== Run #5 Model Status Check ===")
            expected_statuses = {
                "chatgpt": "needs_rerun_context_polluted",
                "kimi": "needs_rerun_placeholder",
                "wenxin": "needs_rerun_placeholder",
                "minimax": "needs_rerun_placeholder",
                "xai": "quota_blocked",
                "claude": "audit_only_refusal",
            }
            for seat, expected_status in expected_statuses.items():
                actual = models.get(seat, {}).get("status", "MISSING")
                ok = actual == expected_status
                print(f"  {'✅' if ok else '❌'} {seat}: expected={expected_status}, got={actual}")
                if not ok:
                    print(f"  [WARN] {seat} status mismatch", file=sys.stderr)
                    has_warning = True
            print()
        except Exception as e:
            print(f"[ERROR] Failed to check run-5.json: {e}", file=sys.stderr)
            has_error = True

    # --- HTML 硬编码残留检查 ---
    print("=== HTML Hardcoded Array Check ===")
    html_path = ROOT / "html" / "index.html"
    if html_path.exists():
        html_content = html_path.read_text(encoding="utf-8")
        # 检查完整数组定义（var XXXXX=[{...}] 形式）
        patterns = [
            (r'var\s+ROUND_RESULTS\s*=\s*\[', "ROUND_RESULTS"),
            (r'var\s+RUN4_MODEL_ARCHIVE\s*=\s*\[', "RUN4_MODEL_ARCHIVE"),
            (r'var\s+RUN5_MODEL_ARCHIVE\s*=\s*\[', "RUN5_MODEL_ARCHIVE"),
        ]
        for pattern, name in patterns:
            match = re.search(pattern, html_content)
            if match:
                # 检查后面是否跟了完整数据对象（不是空数组引用）
                after = html_content[match.end():match.end()+10]
                if after.strip().startswith('{') or after.strip().startswith('['):
                    # 有完整数据对象 — hard fail
                    print(f"  ❌ {name}: 仍有完整硬编码数组定义")
                    has_error = True
                else:
                    print(f"  ✅ {name}: 已改为 API 加载引用")
            else:
                print(f"  ✅ {name}: 无硬编码定义")

        # 检查 fetch 调用
        if "fetch('/api/pool/frontend-archives')" in html_content or 'fetch("/api/pool/frontend-archives")' in html_content:
            print(f"  ✅ fetch('/api/pool/frontend-archives'): 存在")
        else:
            print(f"  ❌ fetch('/api/pool/frontend-archives'): 缺失")
            has_error = True
    else:
        print(f"  ⚠️ html/index.html not found")
    print()

    # --- app.py 路由检查 ---
    print("=== app.py Route Check ===")
    app_path = ROOT / "app.py"
    if app_path.exists():
        app_content = app_path.read_text(encoding="utf-8")
        routes = [
            '/api/pool/models',
            '/api/pool/frontend-archives',
            '/api/pool/model-runs',
            '/api/pool/model-outputs',
            '/api/pool/rerun-queue',
        ]
        for route in routes:
            if route in app_content:
                print(f"  ✅ {route}: 存在")
            else:
                print(f"  ❌ {route}: 缺失")
                has_error = True
    else:
        print(f"  ⚠️ app.py not found")
    print()

    # --- P9.3 状态机数据完整性检查 ---
    print("=== P9.3 State Machine Integrity Check ===")
    mr_path = DATA / "model_runs" / "run-5.json"
    rq_path = DATA / "rerun_queue" / "run-5.json"

    # 检查 1: model_runs.summary.total = 13
    if mr_path.exists():
        try:
            mr = json.loads(mr_path.read_text(encoding="utf-8"))
            total = mr.get("summary", {}).get("total", 0)
            if total == 13:
                print(f"  ✅ model_runs.summary.total = {total}")
            else:
                print(f"  ❌ model_runs.summary.total = {total} (expected 13)")
                has_error = True

            # 检查 5: Run #5 负面状态被识别
            runs = mr.get("runs", [])
            negative_statuses = {"placeholder_only", "context_polluted", "quota_blocked", "auth_blocked", "timeout", "parse_error"}
            negative_models = [r for r in runs if r.get("status") in negative_statuses]
            if negative_models:
                print(f"  ✅ Run #5 negative statuses identified: {len(negative_models)} models")
                for nm in negative_models:
                    print(f"       - {nm['model_account']}: {nm['status']}")
            else:
                print(f"  ❌ Run #5 no negative statuses found (expected at least 5)")
                has_error = True

            # 检查 7: eligible_for_consensus=true 只能出现在 valid_receipt
            bad_eligible = [r for r in runs if r.get("eligible_for_consensus") and r.get("status") != "valid_receipt"]
            if bad_eligible:
                print(f"  ❌ Non-valid_receipt models with eligible_for_consensus=true: {[r['model_account'] for r in bad_eligible]}")
                has_error = True
            else:
                print(f"  ✅ eligible_for_consensus=true only on valid_receipt")

            # 检查 8: risk_refusal 不进入投注共识
            risk_models = [r for r in runs if r.get("status") == "risk_refusal"]
            risk_eligible = [r for r in risk_models if r.get("eligible_for_consensus")]
            if risk_eligible:
                print(f"  ❌ risk_refusal models with eligible_for_consensus=true: {[r['model_account'] for r in risk_eligible]}")
                has_error = True
            else:
                print(f"  ✅ risk_refusal models excluded from consensus")
        except Exception as e:
            print(f"  ❌ Failed to check model_runs: {e}")
            has_error = True
    else:
        print(f"  ❌ model_runs/run-5.json not found")
        has_error = True

    # 检查 6: rerun_queue 不为空
    if rq_path.exists():
        try:
            rq = json.loads(rq_path.read_text(encoding="utf-8"))
            queue = rq.get("queue", [])
            if queue:
                print(f"  ✅ rerun_queue has {len(queue)} entries")
                # 验证入队状态正确
                rerun_entry_statuses = {"placeholder_only", "context_polluted", "quota_blocked", "auth_blocked", "timeout", "parse_error"}
                for q in queue:
                    if q.get("current_status") not in rerun_entry_statuses:
                        print(f"       ⚠️ {q['model_account']}: {q['current_status']} should not be in rerun_queue")
                        has_warning = True
            else:
                print(f"  ❌ rerun_queue is empty (expected entries)")
                has_error = True
        except Exception as e:
            print(f"  ❌ Failed to check rerun_queue: {e}")
            has_error = True
    else:
        print(f"  ❌ rerun_queue/run-5.json not found")
        has_error = True
    print()

    # --- P9.4 每日报告检查 ---
    print("=== P9.4 Daily Report Check ===")
    dr_json = DATA / "daily_reports" / "2026-06-03_run-5.json"
    dr_md   = DATA / "daily_reports" / "2026-06-03_run-5.md"

    # 检查文件存在性
    json_exists = dr_json.exists()
    md_exists   = dr_md.exists()
    print(f"  {'✅' if json_exists else '❌'} data/pool/daily_reports/2026-06-03_run-5.json: {'exists' if json_exists else 'NOT FOUND'}")
    print(f"  {'✅' if md_exists else '❌'} data/pool/daily_reports/2026-06-03_run-5.md: {'exists' if md_exists else 'NOT FOUND'}")
    if not json_exists:
        print(f"       ⚠️ P9.4 report not yet generated (run generate_daily_pool_report.py first)")
        has_warning = True
    if not md_exists:
        has_warning = True

    # JSON 报告内容检查
    if json_exists:
        try:
            dr_data = json.loads(dr_json.read_text(encoding="utf-8"))
            # 可解析
            print(f"  ✅ JSON 报告可解析")

            # summary.total_models = 13
            total_m = dr_data.get("summary", {}).get("total_models")
            if total_m == 13:
                print(f"  ✅ summary.total_models = {total_m}")
            else:
                print(f"  ❌ summary.total_models = {total_m} (expected 13)")
                has_error = True

            # summary.total_matches = 21
            total_matches = dr_data.get("summary", {}).get("total_matches")
            if total_matches == 21:
                print(f"  ✅ summary.total_matches = {total_matches}")
            else:
                print(f"  ❌ summary.total_matches = {total_matches} (expected 21)")
                has_error = True

            # 包含 model_status_counts
            if "model_status_counts" in dr_data and dr_data["model_status_counts"]:
                print(f"  ✅ JSON 含 model_status_counts")
            else:
                print(f"  ❌ JSON 缺少 model_status_counts")
                has_error = True

            # 包含 data_gaps
            if "data_gaps" in dr_data and isinstance(dr_data["data_gaps"], list):
                print(f"  ✅ JSON 含 data_gaps ({len(dr_data['data_gaps'])} items)")
            else:
                print(f"  ❌ JSON 缺少 data_gaps")
                has_error = True

            # 包含 next_actions
            if "next_actions" in dr_data and isinstance(dr_data["next_actions"], list):
                print(f"  ✅ JSON 含 next_actions ({len(dr_data['next_actions'])} items)")
            else:
                print(f"  ❌ JSON 缺少 next_actions")
                has_error = True

        except Exception as e:
            print(f"  ❌ JSON 报告解析失败: {e}")
            has_error = True

    # Markdown 内容检查
    if md_exists:
        try:
            md_content = dr_md.read_text(encoding="utf-8")
            md_checks = ["模型状态统计", "需要补跑", "数据缺口", "下一步动作"]
            for keyword in md_checks:
                if keyword in md_content:
                    print(f"  ✅ Markdown 含 '{keyword}'")
                else:
                    print(f"  ❌ Markdown 缺少 '{keyword}'")
                    has_error = True
        except Exception as e:
            print(f"  ❌ Markdown 读取失败: {e}")
            has_error = True

    print()

    # --- P10.0 Match Results & Snapshots Check ---
    print("=== P10.0 Match Results & Snapshots Check ===")

    # 1. matches/current.json exists and has 21
    matches_cur = DATA / "matches" / "current.json"
    if matches_cur.exists():
        try:
            mc = json.loads(matches_cur.read_text(encoding="utf-8"))
            mc_count = len(mc.get("matches", []))
            if mc_count == 21:
                print(f"  ✅ data/pool/matches/current.json: {mc_count} matches")
            else:
                print(f"  ❌ data/pool/matches/current.json: {mc_count} matches (expected 21)")
                has_error = True
        except Exception as e:
            print(f"  ❌ matches/current.json parse failed: {e}")
            has_error = True
    else:
        print(f"  ❌ data/pool/matches/current.json: NOT FOUND")
        has_error = True

    # 2. matches/snapshots/2026-06-03.json
    matches_snap = DATA / "matches" / "snapshots" / "2026-06-03.json"
    if matches_snap.exists():
        try:
            ms = json.loads(matches_snap.read_text(encoding="utf-8"))
            ms_count = len(ms.get("matches", []))
            if ms_count == 21:
                print(f"  ✅ data/pool/matches/snapshots/2026-06-03.json: {ms_count} matches")
            else:
                print(f"  ❌ matches snapshot: {ms_count} matches (expected 21)")
                has_error = True
        except Exception as e:
            print(f"  ❌ matches snapshot parse failed: {e}")
            has_error = True
    else:
        print(f"  ⚠️ data/pool/matches/snapshots/2026-06-03.json: NOT YET GENERATED (run sync_matches.py)")
        has_warning = True

    # 3. match_results/2026-06-03.json
    mr_path = DATA / "match_results" / "2026-06-03.json"
    if mr_path.exists():
        try:
            mr = json.loads(mr_path.read_text(encoding="utf-8"))
            mr_count = len(mr.get("results", []))
            mr_summary = mr.get("summary", {})
            if mr_count == 21:
                print(f"  ✅ data/pool/match_results/2026-06-03.json: {mr_count} results")
            else:
                print(f"  ❌ match results: {mr_count} results (expected 21)")
                has_error = True

            print(f"       finished: {mr_summary.get('finished', 0)}, scheduled: {mr_summary.get('scheduled', 0)}, missing_or_not_finished: {mr_summary.get('missing_or_not_finished', 0)}")

            # 4-7. Per-result field checks
            required_fields = ["match_id", "status", "home_score", "away_score", "provider", "source_url", "fetched_at", "confidence"]
            missing_field_count = 0
            null_score_count = 0
            for r in mr.get("results", []):
                for f in required_fields:
                    if f not in r:
                        missing_field_count += 1
                # 8. null scores must have result_state
                if r.get("home_score") is None and r.get("away_score") is None:
                    null_score_count += 1
                    if r.get("result_state") not in ("missing_or_not_finished",):
                        print(f"       ⚠️ {r.get('match_id')}: null scores but result_state={r.get('result_state', 'MISSING')}")
                        has_warning = True

            if missing_field_count == 0:
                print(f"  ✅ All result records have required fields")
            else:
                print(f"  ❌ {missing_field_count} missing required fields across results")
                has_error = True

            if null_score_count == mr_count:
                print(f"  ✅ All {null_score_count} results with null scores have result_state set")

            # 9. No high-confidence scores without source
            high_conf_no_source = [r for r in mr.get("results", []) if r.get("confidence", 0) > 0.5 and not r.get("source_url")]
            if high_conf_no_source:
                print(f"  ❌ {len(high_conf_no_source)} results with high confidence but no source_url")
                has_error = True
            else:
                print(f"  ✅ No results with high confidence and missing source_url")

        except Exception as e:
            print(f"  ❌ match_results parse failed: {e}")
            has_error = True
    else:
        print(f"  ⚠️ data/pool/match_results/2026-06-03.json: NOT YET GENERATED (run sync_results.py)")
        has_warning = True

    print()

    # --- P10.1 Odds Snapshots Check ---
    print("=== P10.1 Odds Snapshots Check ===")

    # 1. index.json exists
    idx_path = DATA / "odds_snapshots" / "index.json"
    if idx_path.exists():
        try:
            idx = json.loads(idx_path.read_text(encoding="utf-8"))
            print(f"  ✅ data/pool/odds_snapshots/index.json: exists")
            snapshots = idx.get("snapshots", [])
            print(f"       snapshots in index: {len(snapshots)}")
        except Exception as e:
            print(f"  ❌ data/pool/odds_snapshots/index.json: parse failed: {e}")
            has_error = True
            snapshots = []
    else:
        print(f"  ⚠️ data/pool/odds_snapshots/index.json: NOT YET GENERATED (run sync_odds_snapshots.py)")
        has_warning = True
        snapshots = []

    # 2. 2026-06-03_T-1h.json exists
    snap_path = DATA / "odds_snapshots" / "2026-06-03_T-1h.json"
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            print(f"  ✅ data/pool/odds_snapshots/2026-06-03_T-1h.json: exists")

            # 3. Snapshot JSON parseable (already did)
            # 4. summary.matches_total = 21
            summary = snap.get("summary", {})
            mt = summary.get("matches_total", 0)
            if mt == 21:
                print(f"  ✅ summary.matches_total = {mt}")
            else:
                print(f"  ❌ summary.matches_total = {mt} (expected 21)")
                has_error = True

            # 5. summary.markets_requested contains moneyline, handicap, total_goals
            mrkt = summary.get("markets_requested", [])
            for mk in ["moneyline", "handicap", "total_goals"]:
                if mk in mrkt:
                    print(f"  ✅ markets_requested contains '{mk}'")
                else:
                    print(f"  ❌ markets_requested missing '{mk}'")
                    has_error = True

            # 6. summary.missing_market_coverage should be 63 (21 matches × 3 markets)
            mmc = summary.get("missing_market_coverage", 0)
            if mmc == 63:
                print(f"  ✅ summary.missing_market_coverage = {mmc}")
            else:
                print(f"  ⚠️ summary.missing_market_coverage = {mmc} (expected 63 for manual_stub)")
                has_warning = True

            # 7. odds rows count (should be 147 for manual_stub: 21×3×? selections)
            odds = snap.get("odds", [])
            print(f"       odds rows: {len(odds)}, valid_odds_rows: {summary.get('valid_odds_rows', 0)}")

            # 8. Per-odds-row field checks
            required_fields = [
                "snapshot_id", "match_id", "market", "selection",
                "odds", "bookmaker_or_provider", "snapshot_label",
                "fetched_at", "source_url", "confidence", "status", "market_rules"
            ]
            missing_field_count = 0
            bad_odds = 0
            bad_confidence = 0
            null_counted_as_valid = 0
            for row in odds:
                for f in required_fields:
                    if f not in row:
                        missing_field_count += 1
                # 9. manual_stub: odds=null, status=missing_market_coverage, confidence=0.0
                if row.get("bookmaker_or_provider") == "manual_stub":
                    if row.get("odds") is not None:
                        bad_odds += 1
                    if row.get("status") != "missing_market_coverage":
                        bad_odds += 1
                    if row.get("confidence", 0) != 0.0:
                        bad_confidence += 1
                # 10. Forbidden checks
                if row.get("odds") is not None and row.get("odds", 0) == 0:
                    print(f"  ❌ odds=0 in row {row.get('snapshot_id', '')}")
                    has_error = True
                if row.get("confidence", 0) > 0.5 and not row.get("source_url"):
                    print(f"  ❌ high confidence but no source_url: {row.get('snapshot_id', '')}")
                    has_error = True
                if row.get("odds") is None and row.get("status") not in (
                    "missing_market_coverage", "match_mapping_failed", "provider_unavailable", "market_not_supported", "manual_review"
                ):
                    null_counted_as_valid += 1

            if missing_field_count == 0:
                print(f"  ✅ All odds rows have required fields")
            else:
                print(f"  ❌ {missing_field_count} missing required fields across odds rows")
                has_error = True

            if bad_odds == 0:
                print(f"  ✅ manual_stub odds=null and status=missing_market_coverage")
            else:
                print(f"  ❌ {bad_odds} manual_stub rows with invalid odds/status")
                has_error = True

            if bad_confidence == 0:
                print(f"  ✅ manual_stub confidence=0.0")
            else:
                print(f"  ❌ {bad_confidence} manual_stub rows with confidence!=0.0")
                has_error = True

            if null_counted_as_valid == 0:
                print(f"  ✅ null odds not counted as valid")
            else:
                print(f"  ⚠️ {null_counted_as_valid} rows with null odds have non-expected status")
                has_warning = True

        except Exception as e:
            print(f"  ❌ odds snapshot parse failed: {e}")
            has_error = True
    else:
        print(f"  ⚠️ data/pool/odds_snapshots/2026-06-03_T-1h.json: NOT YET GENERATED")
        has_warning = True

    print()

    # --- P10.2 Bet Receipts Check ---
    print("=== P10.2 Bet Receipts Check ===")

    # 1-3. Check files exist
    br_path = DATA / "bet_receipts" / "run-5.json"
    rj_path = DATA / "bet_receipts" / "rejections" / "run-5.json"
    idx_br = DATA / "bet_receipts" / "index.json"

    br_data = None
    rj_data = None

    for label, path in [("bet_receipts/run-5.json", br_path),
                        ("bet_receipts/rejections/run-5.json", rj_path),
                        ("bet_receipts/index.json", idx_br)]:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                print(f"  ✅ data/pool/{label}: exists")
                if "bet_receipts/run-5.json" in label and "rejections" not in label:
                    br_data = data
                if "rejections/run-5" in label:
                    rj_data = data
            except Exception as e:
                print(f"  ❌ data/pool/{label}: parse failed: {e}")
                has_error = True
        else:
            print(f"  ⚠️ data/pool/{label}: NOT YET GENERATED (run validate_model_outputs.py)")
            has_warning = True

    # 4-7. Content checks
    if br_data:
        summary = br_data.get("summary", {})
        mt = summary.get("models_total", 0)
        ab = summary.get("accepted_bets", 0)
        vfs = summary.get("valid_for_settlement", False)

        if mt == 13:
            print(f"  ✅ summary.models_total = 13")
        else:
            print(f"  ❌ summary.models_total = {mt} (expected 13)")
            has_error = True

        print(f"       accepted_bets = {ab}")
        print(f"       valid_for_settlement = {vfs}")

        # 6. manual_stub: accepted_bets=0 is allowed
        if ab == 0:
            print(f"  ✅ accepted_bets=0 (expected with manual_stub)")
        else:
            print(f"  ℹ️  accepted_bets > 0")

        # 7. If valid_for_settlement=true, must have accepted bets with valid odds
        if vfs:
            if ab > 0:
                # Check accepted receipts have valid odds
                for receipt in br_data.get("accepted_receipts", []):
                    for bet_entry in receipt.get("receipt", {}).get("bet_ledger", []):
                        if bet_entry.get("odds") is None or bet_entry.get("odds", 0) <= 1:
                            print(f"  ❌ accepted bet has invalid odds: {bet_entry}")
                            has_error = True
                print(f"  ✅ valid_for_settlement with accepted_bets > 0")
            else:
                print(f"  ❌ valid_for_settlement=true but accepted_bets=0")
                has_error = True

        # 8. No odds=null in accepted
        null_odds = 0
        for receipt in br_data.get("accepted_receipts", []):
            for bet_entry in receipt.get("receipt", {}).get("bet_ledger", []):
                if bet_entry.get("odds") is None:
                    null_odds += 1
        if null_odds == 0:
            print(f"  ✅ No odds=null in accepted receipts")
        else:
            print(f"  ❌ {null_odds} bets with odds=null in accepted")
            has_error = True

        # 9. manual_stub missing odds not in accepted
        missing_in_accepted = 0
        for receipt in br_data.get("accepted_receipts", []):
            for bet_entry in receipt.get("receipt", {}).get("bet_ledger", []):
                status = bet_entry.get("status", "")
                odds = bet_entry.get("odds")
                if status == "missing_market_coverage" or (odds is None):
                    missing_in_accepted += 1
        if missing_in_accepted == 0:
            print(f"  ✅ manual_stub missing odds not in accepted")
        else:
            print(f"  ❌ {missing_in_accepted} manual_stub missing odds in accepted")
            has_error = True

    # 10. Rejections have reason counts
    if rj_data:
        rc = rj_data.get("summary", {}).get("reason_counts", {})
        print(f"       rejection reason_counts: {rc}")
        if rc:
            print(f"  ✅ rejections have reason_counts")
        else:
            print(f"  ❌ rejections missing reason_counts")
            has_error = True

    # ── P10.3 Settlement Check ──────────────────────────────────────────────
    print("\n=== P10.3 Settlement Check ===")
    settle_path = DATA / "settlements" / "run-5.json"
    settle_idx_path = DATA / "settlements" / "index.json"
    settle_md_path = DATA / "daily_reports" / "settlement_run-5.md"

    # 1-3. File existence
    st_data = None
    for label, path in [("settlements/run-5.json", settle_path),
                        ("settlements/index.json", settle_idx_path),
                        ("daily_reports/settlement_run-5.md", settle_md_path)]:
        if path.exists():
            if path.suffix == ".json":
                try:
                    d = json.loads(path.read_text(encoding="utf-8"))
                    print(f"  ✅ data/pool/{label}: exists")
                    if "settlements/run-5.json" in label:
                        st_data = d
                except Exception as e:
                    print(f"  ❌ data/pool/{label}: parse failed: {e}")
                    has_error = True
            else:
                print(f"  ✅ data/pool/{label}: exists")
        else:
            print(f"  ⚠️ data/pool/{label}: NOT YET GENERATED (run settle_pool_round.py)")
            has_warning = True

    if st_data:
        # 4. JSON parseable (already handled above)
        # 5. settlement_status
        ss = st_data.get("settlement_status")
        expected_ss = "no_bets_to_settle"
        if ss == expected_ss:
            print(f"  ✅ settlement_status = {ss}")
        else:
            print(f"  ❌ settlement_status = {ss} (expected {expected_ss})")
            has_error = True

        # 6-8. Summary checks
        summary = st_data.get("summary", {})
        ab = summary.get("accepted_bets", -1)
        sb = summary.get("settled_bets", -1)
        tp = summary.get("total_profit", "missing")
        roi = summary.get("roi", "missing")

        if ab == 0:
            print(f"  ✅ summary.accepted_bets = 0")
        else:
            print(f"  ❌ summary.accepted_bets = {ab} (expected 0)")
            has_error = True

        if sb == 0:
            print(f"  ✅ summary.settled_bets = 0")
        else:
            print(f"  ❌ summary.settled_bets = {sb} (expected 0)")
            has_error = True

        if tp is None:
            print(f"  ✅ summary.total_profit = null")
        else:
            print(f"  ❌ summary.total_profit = {tp} (expected null)")
            has_error = True

        if roi is None:
            print(f"  ✅ summary.roi = null")
        else:
            print(f"  ❌ summary.roi = {roi} (expected null)")
            has_error = True

        # 9. valid_for_leaderboard_update
        vlb = st_data.get("valid_for_leaderboard_update")
        if vlb is False:
            print(f"  ✅ valid_for_leaderboard_update = false")
        else:
            print(f"  ❌ valid_for_leaderboard_update = {vlb} (expected false)")
            has_error = True

    # 10-12. Markdown content checks
    if settle_md_path.exists():
        md_content = settle_md_path.read_text(encoding="utf-8")
        md_checks = [
            ("结算结论", "结算结论"),
            ("没有 ROI", "没有 ROI"),
            ("accepted_bets=0", "accepted_bets=0"),
        ]
        for label, keyword in md_checks:
            if keyword in md_content:
                print(f"  ✅ Markdown 包含 '{keyword}'")
            else:
                print(f"  ❌ Markdown 缺少 '{keyword}'")
                has_error = True

    print()

    # ── P11.0 Run Manifest / Prompts / Ingest Check ─────────────────────────
    print("=== P11.0 Run Manifest / Prompts / Ingest Check ===")
    manifest_path = DATA / "run_manifests" / "run-6.json"
    prompts_dir = DATA / "prompts" / "run-6"
    ingested_path = DATA / "model_outputs" / "ingested" / "run-6" / "index.json"
    raw_dir = DATA / "model_outputs" / "raw" / "run-6"

    # 1. Manifest exists
    if manifest_path.exists():
        try:
            mf = json.loads(manifest_path.read_text(encoding="utf-8"))
            seats_mf = mf.get("seats_total", -1)
            print(f"  ✅ data/pool/run_manifests/run-6.json: exists (seats_total={seats_mf})")
            if seats_mf != 13:
                print(f"  ❌ seats_total={seats_mf}, expected 13")
                has_error = True
        except Exception:
            print(f"  ❌ data/pool/run_manifests/run-6.json: parse failed")
            has_error = True
    else:
        print(f"  ⚠️ data/pool/run_manifests/run-6.json: NOT YET GENERATED")
        has_warning = True

    # 2-4. Prompts directory and content
    if prompts_dir.exists():
        md_files = sorted(prompts_dir.glob("*.md"))
        prompt_count = len(md_files)
        if prompt_count == 13:
            print(f"  ✅ data/pool/prompts/run-6/: {prompt_count} prompts")
        else:
            print(f"  ❌ prompt count={prompt_count}, expected 13")
            has_error = True

        all_prompts_ok = 0
        for p in md_files[:5]:  # 检查前 5 个
            text = p.read_text()
            checks_ok = True
            for kw in ["AI_JUDGE_RUN_MARKER", "round_id: run-6", "bet_ledger"]:
                if kw not in text:
                    checks_ok = False
                    break
            if checks_ok:
                all_prompts_ok += 1
        if all_prompts_ok >= 5:
            print(f"  ✅ first 5 prompts contain required keywords")
        else:
            print(f"  ❌ some prompts missing required keywords")
            has_error = True

        # 防污染说明检查
        anti_pollution_found = False
        for p in md_files[:3]:
            text = p.read_text()
            if "狼人杀" in text:
                anti_pollution_found = True
                break
        if anti_pollution_found:
            print(f"  ✅ prompts contain anti-pollution wording (狼人杀)")
        else:
            print(f"  ⚠️ prompts may lack anti-pollution wording")
            has_warning = True
    else:
        print(f"  ⚠️ data/pool/prompts/run-6/: NOT YET GENERATED")
        has_warning = True

    # 5-8. Ingested outputs
    if ingested_path.exists():
        try:
            ig = json.loads(ingested_path.read_text(encoding="utf-8"))
            ot = ig.get("outputs_total", -1)
            of = ig.get("outputs_found", -1)
            om = ig.get("outputs_missing", -1)
            print(f"  ✅ ingested/run-6/index.json: total={ot}, found={of}, missing={om}")
            if ot != 13:
                print(f"  ❌ outputs_total={ot}, expected 13")
                has_error = True
            if of != 0:
                print(f"  ❌ outputs_found={of}, expected 0 (no raw outputs yet)")
                has_error = True
            if om != 13:
                print(f"  ❌ outputs_missing={om}, expected 13")
                has_error = True
        except Exception:
            print(f"  ❌ ingested/run-6/index.json: parse failed")
            has_error = True
    else:
        print(f"  ⚠️ ingested/run-6/index.json: NOT YET GENERATED")
        has_warning = True

    # 9. State is waiting_for_manual_ingest, not failure
    raw_files_found = 0
    if raw_dir.exists():
        raw_files_found = len([p for p in raw_dir.glob("*.txt") if p.stat().st_size > 50])
    if raw_files_found == 0 and ingested_path.exists():
        print(f"  ✅ state: waiting_for_manual_ingest (correct)")
    elif raw_files_found == 0 and not ingested_path.exists():
        print(f"  ⚠️ state: waiting_for_manual_ingest (ingest not yet run)")
        has_warning = True
    else:
        print(f"  ⚠️ state: has raw outputs, ready for pipeline")

    print()

    # --- P11.1 补跑机制检查 ---
    print("=== P11.1 Rerun Failed Seats Check ===")

    rerun_attempts_path = DATA / "rerun_attempts" / "run-5.json"
    rerun_prompts_dir = DATA / "prompts" / "rerun" / "run-5" / "attempt-2"
    rerun_ingested_path = DATA / "model_outputs" / "ingested_rerun" / "run-5" / "attempt-2" / "index.json"

    # 1. rerun_attempts/run-5.json 存在
    if rerun_attempts_path.exists():
        try:
            ra = json.loads(rerun_attempts_path.read_text(encoding="utf-8"))
            rs = ra.get("summary", {})
            qt = rs.get("queue_total", -1)
            pa = rs.get("planned_attempts", -1)
            print(f"  ✅ data/pool/rerun_attempts/run-5.json: exists (queue_total={qt}, planned_attempts={pa})")
            if qt != 5:
                print(f"  ❌ queue_total={qt}, expected 5")
                has_error = True
            if pa != 5:
                print(f"  ❌ planned_attempts={pa}, expected 5")
                has_error = True
        except Exception:
            print(f"  ❌ rerun_attempts/run-5.json: parse failed")
            has_error = True
    else:
        print(f"  ❌ data/pool/rerun_attempts/run-5.json: NOT FOUND")
        has_error = True

    # 4-5. prompt 目录和数量
    if rerun_prompts_dir.exists():
        prompt_files = sorted(rerun_prompts_dir.glob("*.md"))
        pc = len(prompt_files)
        print(f"  ✅ data/pool/prompts/rerun/run-5/attempt-2/: {pc} prompts")
        if pc != 5:
            print(f"  ❌ prompt count={pc}, expected 5")
            has_error = True

        # 6. 每个 prompt 包含必要内容
        all_prompts_ok = True
        for pf in prompt_files:
            text = pf.read_text(encoding="utf-8")
            checks = [
                ("AI_JUDGE_RERUN_MARKER", "AI_JUDGE_RERUN_MARKER" in text),
                ("attempt_no: 2", "attempt_no: 2" in text),
                ("round_id: run-5", "round_id: run-5" in text),
                ("previous_status", "previous_status" in text),
                ("bet_ledger", "bet_ledger" in text),
                ("只输出 JSON", "只输出标准 JSON" in text or "只输出 JSON" in text or "只输出一个 JSON" in text),
            ]
            for check_name, ok in checks:
                if not ok:
                    print(f"  ❌ {pf.name}: missing '{check_name}'")
                    all_prompts_ok = False
        if all_prompts_ok:
            print(f"  ✅ all 5 prompts contain required keywords")
    else:
        print(f"  ❌ data/pool/prompts/rerun/run-5/attempt-2/: NOT FOUND")
        has_error = True

    # 7-10. ingested_rerun index
    if rerun_ingested_path.exists():
        try:
            ig = json.loads(rerun_ingested_path.read_text(encoding="utf-8"))
            ot = ig.get("outputs_total", -1)
            of = ig.get("outputs_found", -1)
            om = ig.get("outputs_missing", -1)
            print(f"  ✅ ingested_rerun/run-5/attempt-2/index.json: total={ot}, found={of}, missing={om}")
            if ot != 5:
                print(f"  ❌ outputs_total={ot}, expected 5")
                has_error = True
            if of != 0:
                print(f"  ❌ outputs_found={of}, expected 0")
                has_error = True
            if om != 5:
                print(f"  ❌ outputs_missing={om}, expected 5")
                has_error = True
        except Exception:
            print(f"  ❌ ingested_rerun/run-5/attempt-2/index.json: parse failed")
            has_error = True
    else:
        print(f"  ⚠️ ingested_rerun/run-5/attempt-2/index.json: NOT YET GENERATED")
        has_warning = True

    # 11. 状态为 waiting_for_rerun_outputs
    if rerun_ingested_path.exists():
        print(f"  ✅ state: waiting_for_rerun_outputs (correct, not a failure)")

    print()

    # --- P11.2 前端五页检查 ---
    print("=== P11.2 Frontend Five-Page Check ===")

    html_path = ROOT / "html" / "index.html"
    if html_path.exists():
        html_text = html_path.read_text(encoding="utf-8")

        # 1. 五个 view 存在
        views = ["view-dashboard", "view-models", "view-match-detail", "view-run-archives", "view-system-health"]
        all_views_found = True
        for v in views:
            if v in html_text:
                print(f"  ✅ {v}: found")
            else:
                print(f"  ❌ {v}: NOT FOUND")
                all_views_found = False
                has_error = True

        # 2. 存在导航按钮
        if "pool-nav" in html_text and "nav-btn" in html_text and "switchPoolView" in html_text:
            print(f"  ✅ pool-nav with nav-btn and switchPoolView: found")
        else:
            print(f"  ❌ pool-nav or nav-btn or switchPoolView: MISSING")
            has_error = True

        # 3-5. API fetch 引用
        api_checks = [
            ("/api/pool/run-manifests/run-6", "run-manifests/run-6 fetch"),
            ("/api/pool/rerun-attempts/run-5", "rerun-attempts/run-5 fetch"),
            ("/api/pool/settlements/run-5", "settlements/run-5 fetch"),
        ]
        for pattern, label in api_checks:
            if pattern in html_text:
                print(f"  ✅ {label}: found")
            else:
                print(f"  ❌ {label}: NOT FOUND")
                has_error = True

        # 6. 不存在完整硬编码档案数组
        hardcoded_patterns = [
            "ROUND_RESULTS = [",
            "RUN4_MODEL_ARCHIVE = [",
            "RUN5_MODEL_ARCHIVE = [",
        ]
        all_hardcoded_clean = True
        for p in hardcoded_patterns:
            if p in html_text:
                print(f"  ❌ hardcoded array found: {p}")
                all_hardcoded_clean = False
                has_error = True
        if all_hardcoded_clean:
            print(f"  ✅ no hardcoded archive arrays detected")

        # 7. 不存在 null score → 0 转换
        if "null" in html_text and ("0-0" in html_text or "score.*0" in html_text):
            # only flag if both null and 0-0 appear in proximity
            print(f"  ⚠️ potential null-score-to-0 pattern (manual review recommended)")
            has_warning = True
        else:
            print(f"  ✅ no obvious null-score-to-0 pattern detected")
    else:
        print(f"  ❌ html/index.html: NOT FOUND")
        has_error = True

    print()

    # ── P12.0 Pipeline Check ──────────────────────────────────────────────────
    print("=== P12.0 Pipeline Check ===")

    # 1. ops/run_daily_pool_pipeline.py 存在
    pipeline_script = ROOT / "ops" / "run_daily_pool_pipeline.py"
    if pipeline_script.exists():
        print(f"  ✅ ops/run_daily_pool_pipeline.py: exists")
    else:
        print(f"  ❌ ops/run_daily_pool_pipeline.py: NOT FOUND")
        has_error = True

    # 2-3. pipeline_runs JSON & MD
    pipeline_json = DATA / "pipeline_runs" / "2026-06-03_run-6.json"
    pipeline_md = DATA / "pipeline_runs" / "2026-06-03_run-6.md"

    json_exists = pipeline_json.exists()
    md_exists = pipeline_md.exists()

    if json_exists:
        print(f"  ✅ data/pool/pipeline_runs/2026-06-03_run-6.json: exists")
    else:
        print(f"  ⚠️  data/pool/pipeline_runs/2026-06-03_run-6.json: NOT YET GENERATED (run pipeline)")
        has_warning = True

    if md_exists:
        print(f"  ✅ data/pool/pipeline_runs/2026-06-03_run-6.md: exists")
    else:
        print(f"  ⚠️  data/pool/pipeline_runs/2026-06-03_run-6.md: NOT YET GENERATED (run pipeline)")
        has_warning = True

    # 4. JSON 可解析
    if json_exists:
        try:
            pdata = json.loads(pipeline_json.read_text(encoding="utf-8"))
            print(f"  ✅ Pipeline JSON 可解析")

            # 5. final_status 在合法值中
            valid_statuses = {"pass", "pass_with_warnings", "blocked", "failed"}
            fs = pdata.get("final_status", "")
            if fs in valid_statuses:
                print(f"  ✅ final_status = {fs} (in {valid_statuses})")
            else:
                print(f"  ❌ final_status = {fs} (not in {valid_statuses})")
                has_error = True

            # 6. steps 数量 > 0
            steps = pdata.get("steps", [])
            if len(steps) > 0:
                print(f"  ✅ steps count = {len(steps)} > 0")
            else:
                print(f"  ❌ steps count = {len(steps)} (expected > 0)")
                has_error = True

            # 7. run-6 waiting_for_manual_ingest 不算 hard failure
            has_waiting = any(
                "waiting_for_manual_ingest" in str(s.get("reason", "")).lower() or
                "waiting_for_manual_ingest" in str(s.get("warnings", "")).lower()
                for s in steps
            )
            if has_waiting:
                print(f"  ✅ run-6 waiting_for_manual_ingest marked (not a hard failure)")
            # (no error even if not present — might be pass)

            # Check for real blockers (not waiting_for_manual_ingest)
            real_blockers = [
                s for s in steps
                if s.get("status") in ("blocked", "failed") and
                "waiting_for_manual_ingest" not in str(s.get("reason", "")).lower() and
                "waiting_for_manual_ingest" not in str(s.get("warnings", "")).lower()
            ]
            if real_blockers:
                print(f"  ⚠️  {len(real_blockers)} real blockers found (not waiting_for_manual_ingest)")
                has_warning = True

        except Exception as e:
            print(f"  ❌ Pipeline JSON parse failed: {e}")
            has_error = True

    # 8. html/index.html 包含 /api/pool/pipeline-runs
    html_path_check = ROOT / "html" / "index.html"
    if html_path_check.exists():
        html_content_check = html_path_check.read_text(encoding="utf-8")
        if "/api/pool/pipeline-runs" in html_content_check:
            print(f"  ✅ html/index.html contains /api/pool/pipeline-runs")
        else:
            print(f"  ❌ html/index.html missing /api/pool/pipeline-runs")
            has_error = True
    else:
        print(f"  ⚠️  html/index.html not found")
        has_warning = True

    print()

    # ── P12.1 Scheduling / Deployment Check ────────────────────────────────────
    print("=== P12.1 Scheduling / Deployment Check ===")

    # 1. .github/workflows/daily-pool-pipeline.yml 存在
    workflow_path = ROOT / ".github" / "workflows" / "daily-pool-pipeline.yml"
    if workflow_path.exists():
        print(f"  ✅ .github/workflows/daily-pool-pipeline.yml: exists")
    else:
        print(f"  ❌ .github/workflows/daily-pool-pipeline.yml: NOT FOUND")
        has_error = True

    # 2. workflow 包含关键元素
    if workflow_path.exists():
        wf_text = workflow_path.read_text(encoding="utf-8")
        checks = {
            "workflow_dispatch": "workflow_dispatch" in wf_text,
            "schedule": "schedule:" in wf_text,
            "run_daily_pool_pipeline.py": "run_daily_pool_pipeline.py" in wf_text,
            "--skip-browser": "--skip-browser" in wf_text,
            "--continue-on-warning": "--continue-on-warning" in wf_text,
        }
        for key, ok in checks.items():
            if ok:
                print(f"  ✅ workflow contains {key}")
            else:
                print(f"  ❌ workflow missing {key}")
                has_error = True

    # 3. docs/P12.1_SCHEDULING.md 存在
    docs_path = ROOT / "docs" / "P12.1_SCHEDULING.md"
    if docs_path.exists():
        print(f"  ✅ docs/P12.1_SCHEDULING.md: exists")
    else:
        print(f"  ❌ docs/P12.1_SCHEDULING.md: NOT FOUND")
        has_error = True

    # 4. vercel.json 存在
    vercel_json = ROOT / "vercel.json"
    if vercel_json.exists():
        print(f"  ✅ vercel.json: exists")
    else:
        print(f"  ❌ vercel.json: NOT FOUND")
        has_error = True

    # 5. vercel.json 包含 /api/cron/pipeline-status
    if vercel_json.exists():
        vj_text = vercel_json.read_text(encoding="utf-8")
        if "/api/cron/pipeline-status" in vj_text:
            print(f"  ✅ vercel.json contains /api/cron/pipeline-status")
        else:
            print(f"  ❌ vercel.json missing /api/cron/pipeline-status")
            has_error = True

    # 6. app.py 包含 /api/cron/pipeline-status
    appy_path = ROOT / "app.py"
    if appy_path.exists():
        appy_text = appy_path.read_text(encoding="utf-8")
        if "/api/cron/pipeline-status" in appy_text:
            print(f"  ✅ app.py contains /api/cron/pipeline-status")
        else:
            print(f"  ❌ app.py missing /api/cron/pipeline-status")
            has_error = True
    else:
        print(f"  ⚠️  app.py not found")
        has_warning = True

    # 7. html/index.html 包含 /api/cron/pipeline-status
    html_path_p121 = ROOT / "html" / "index.html"
    if html_path_p121.exists():
        html_content_p121 = html_path_p121.read_text(encoding="utf-8")
        if "/api/cron/pipeline-status" in html_content_p121:
            print(f"  ✅ html/index.html contains /api/cron/pipeline-status")
        else:
            print(f"  ❌ html/index.html missing /api/cron/pipeline-status")
            has_error = True
    else:
        print(f"  ⚠️  html/index.html not found")
        has_warning = True

    # 8. 当前 pipeline run JSON 仍可读取
    if json_exists:
        try:
            pdata2 = json.loads(pipeline_json.read_text(encoding="utf-8"))
            print(f"  ✅ Pipeline JSON still readable (final_status={pdata2.get('final_status')})")
        except Exception as e:
            print(f"  ❌ Pipeline JSON re-read failed: {e}")
            has_error = True

    # 9. workflow 不默认调用浏览器（已由 --skip-browser 保证）
    if workflow_path.exists():
        if "--skip-browser" in wf_text:
            print(f"  ✅ workflow uses --skip-browser (no browser call by default)")
        else:
            print(f"  ❌ workflow does not use --skip-browser")
            has_error = True

    # ── P12.2 Production Ops Checks ────────────────────────────────────
    print("=== P12.2 Production Ops Check ===")

    # 1. docs/PRODUCTION_RUNBOOK.md 存在
    pr_doc = DOCS_DIR / "PRODUCTION_RUNBOOK.md"
    if pr_doc.exists():
        print(f"  ✅ docs/PRODUCTION_RUNBOOK.md: exists")
    else:
        print(f"  ❌ docs/PRODUCTION_RUNBOOK.md: NOT FOUND")
        has_error = True

    # 2. docs/ALERTING_POLICY.md 存在
    ap_doc = DOCS_DIR / "ALERTING_POLICY.md"
    if ap_doc.exists():
        print(f"  ✅ docs/ALERTING_POLICY.md: exists")
    else:
        print(f"  ❌ docs/ALERTING_POLICY.md: NOT FOUND")
        has_error = True

    # 3. docs/INCIDENT_PLAYBOOK.md 存在
    ip_doc = DOCS_DIR / "INCIDENT_PLAYBOOK.md"
    if ip_doc.exists():
        print(f"  ✅ docs/INCIDENT_PLAYBOOK.md: exists")
    else:
        print(f"  ❌ docs/INCIDENT_PLAYBOOK.md: NOT FOUND")
        has_error = True

    # 4. docs/OPERATIONS_CHECKLIST.md 存在
    oc_doc = DOCS_DIR / "OPERATIONS_CHECKLIST.md"
    if oc_doc.exists():
        print(f"  ✅ docs/OPERATIONS_CHECKLIST.md: exists")
    else:
        print(f"  ❌ docs/OPERATIONS_CHECKLIST.md: NOT FOUND")
        has_error = True

    # 5. ops/check_ops_readiness.py 存在
    cor_path = OPS_DIR / "check_ops_readiness.py"
    if cor_path.exists():
        print(f"  ✅ ops/check_ops_readiness.py: exists")
    else:
        print(f"  ❌ ops/check_ops_readiness.py: NOT FOUND")
        has_error = True

    # 6. data/pool/ops_readiness/latest.json 存在
    or_json = DATA / "ops_readiness" / "latest.json"
    or_exists = or_json.exists()
    if or_exists:
        print(f"  ✅ data/pool/ops_readiness/latest.json: exists")
    else:
        print(f"  ⚠️  data/pool/ops_readiness/latest.json: NOT FOUND (run ops/check_ops_readiness.py to generate)")
        has_warning = True

    # 7. ops readiness JSON 可解析
    if or_exists:
        try:
            or_data = json.loads(or_json.read_text(encoding="utf-8"))
            print(f"  ✅ ops readiness JSON 可解析 (overall_status={or_data.get('overall_status', 'N/A')})")
        except Exception as e:
            print(f"  ❌ ops readiness JSON parse error: {e}")
            has_error = True

    # 8. overall_status in allowed states
    if or_exists:
        try:
            or_data2 = json.loads(or_json.read_text(encoding="utf-8"))
            os_val = or_data2.get("overall_status", "")
            if os_val in ("ready", "ready_with_warnings", "blocked", "missing"):
                print(f"  ✅ overall_status = {os_val} (allowed)")
            else:
                print(f"  ❌ overall_status = {os_val} (NOT allowed)")
                has_error = True
        except Exception:
            pass  # already reported above

    # 9. app.py 包含 /api/pool/ops-readiness
    if APP_FILE.exists():
        appy2_text = APP_FILE.read_text(encoding="utf-8")
        if "/api/pool/ops-readiness" in appy2_text:
            print(f"  ✅ app.py contains /api/pool/ops-readiness")
        else:
            print(f"  ❌ app.py missing /api/pool/ops-readiness")
            has_error = True
    else:
        print(f"  ⚠️  app.py not found (should not happen)")
        has_warning = True

    # 10. html/index.html 包含 /api/pool/ops-readiness
    if HTML_FILE.exists():
        html2_text = HTML_FILE.read_text(encoding="utf-8")
        if "/api/pool/ops-readiness" in html2_text:
            print(f"  ✅ html/index.html contains /api/pool/ops-readiness")
        else:
            print(f"  ❌ html/index.html missing /api/pool/ops-readiness")
            has_error = True
    else:
        print(f"  ⚠️  html/index.html not found")
        has_warning = True

    # 11. Alerting docs 包含 waiting_for_manual_ingest
    if ap_doc.exists():
        ap_text = ap_doc.read_text(encoding="utf-8")
        if "waiting_for_manual_ingest" in ap_text:
            print(f"  ✅ ALERTING_POLICY.md contains waiting_for_manual_ingest")
        else:
            print(f"  ⚠️  ALERTING_POLICY.md missing waiting_for_manual_ingest (recommended)")
            has_warning = True

    # 12. Incident playbook 包含 GitHub remote 404
    if ip_doc.exists():
        ip_text = ip_doc.read_text(encoding="utf-8")
        if "GitHub remote 404" in ip_text or "remote 404" in ip_text.lower():
            print(f"  ✅ INCIDENT_PLAYBOOK.md covers GitHub remote 404")
        else:
            print(f"  ⚠️  INCIDENT_PLAYBOOK.md does not cover GitHub remote 404")
            has_warning = True

    # ── P13.0 Real Provider / Model Output Checks ──────────────
    print("=== P13.0 Real Provider / Model Output Check ===")

    # 1. ops/check_provider_config.py 存在
    cpc_path = ROOT / "ops" / "check_provider_config.py"
    if cpc_path.exists():
        print(f"  ✅ ops/check_provider_config.py: exists")
    else:
        print(f"  ❌ ops/check_provider_config.py: NOT FOUND")
        has_error = True

    # 2. data/pool/provider_status/latest.json 存在
    ps_json = DATA / "provider_status" / "latest.json"
    ps_exists = ps_json.exists()
    if ps_exists:
        print(f"  ✅ data/pool/provider_status/latest.json: exists")
    else:
        print(f"  ⚠️  data/pool/provider_status/latest.json: NOT FOUND (run check_provider_config.py to generate)")
        has_warning = True

    # 3. ops/check_model_output_dropbox.py 存在
    cmod_path = ROOT / "ops" / "check_model_output_dropbox.py"
    if cmod_path.exists():
        print(f"  ✅ ops/check_model_output_dropbox.py: exists")
    else:
        print(f"  ❌ ops/check_model_output_dropbox.py: NOT FOUND")
        has_error = True

    # 4. data/pool/model_outputs/raw/run-6/README.md 存在
    readme_path = DATA / "model_outputs" / "raw" / "run-6" / "README.md"
    if readme_path.exists():
        print(f"  ✅ data/pool/model_outputs/raw/run-6/README.md: exists")
    else:
        print(f"  ⚠️  README.md not found (optional but recommended)")
        has_warning = True

    # 5. data/pool/model_outputs/raw/run-6/dropbox_check.json 存在
    dbc_json = DATA / "model_outputs" / "raw" / "run-6" / "dropbox_check.json"
    dbc_exists = dbc_json.exists()
    if dbc_exists:
        print(f"  ✅ dropbox_check.json: exists")
    else:
        print(f"  ⚠️  dropbox_check.json: NOT FOUND (run check_model_output_dropbox.py to generate)")
        has_warning = True

    # 6. dropbox status 合法
    if dbc_exists:
        try:
            dbc_data = json.loads(dbc_json.read_text(encoding="utf-8"))
            dbc_status = dbc_data.get("status", "")
            if dbc_status in ("waiting_for_manual_ingest", "partial_outputs_found", "ready_for_ingest"):
                print(f"  ✅ dropbox status = {dbc_status} (allowed)")
            else:
                print(f"  ❌ dropbox status = {dbc_status} (NOT allowed)")
                has_error = True
        except Exception as e:
            print(f"  ❌ dropbox_check.json parse error: {e}")
            has_error = True

    # 7. app.py 包含 /api/pool/provider-status
    if APP_FILE.exists():
        app_text = APP_FILE.read_text(encoding="utf-8")
        if "/api/pool/provider-status" in app_text:
            print(f"  ✅ app.py contains /api/pool/provider-status")
        else:
            print(f"  ❌ app.py missing /api/pool/provider-status")
            has_error = True

    # 8. app.py 包含 provider-specific odds snapshot route
    if APP_FILE.exists():
        app_text2 = APP_FILE.read_text(encoding="utf-8")
        if "/api/pool/odds-snapshots" in app_text2 and "provider" in app_text2:
            print(f"  ✅ app.py contains provider-specific odds snapshot route")
        else:
            print(f"  ⚠️  app.py may be missing provider-specific odds route")
            has_warning = True

    # 9. No API keys in repo
    git_files = []
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        git_files = result.stdout.strip().splitlines()
    except Exception:
        pass

    key_patterns = ["THE_ODDS_API_KEY=", "sk_live_", "api_key", "secret_key"]
    found_keys = []
    for fname in git_files:
        fpath = ROOT / fname
        if not fpath.exists():
            continue
        if fpath.suffix in (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf"):
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            for pat in key_patterns:
                if pat in content and "os.environ.get" not in content:
                    found_keys.append(f"{fname}: contains '{pat}'")
        except Exception:
            continue

    if found_keys:
        print(f"  ❌ Potential API keys found in repo:")
        for fk in found_keys[:5]:
            print(f"       {fk}")
        has_error = True
    else:
        print(f"  ✅ No API keys detected in tracked files")

    # 10. Provider not configured = warning (not system failure)
    if ps_exists:
        try:
            ps_data = json.loads(ps_json.read_text(encoding="utf-8"))
            for p in ps_data.get("providers", []):
                if not p.get("configured"):
                    print(f"  ✅ provider {p.get('provider')} not configured — recorded as warning (not system failure)")
        except Exception:
            pass

    print()

    # --- 汇总 ---
    print("=== Summary ===")
    all_valid = all(r["valid_json"] for r in results)
    all_exist = all(r["exists"] for r in results)
    print(f"  All files exist:   {all_exist}")
    print(f"  All JSON valid:    {all_valid}")
    print(f"  Has hard error:    {has_error}")
    print(f"  Has warning:       {has_warning}")

    if has_error:
        print("\n❌ CHECK FAILED — exiting with code 1")
        sys.exit(1)
    else:
        print("\n✅ CHECK PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
