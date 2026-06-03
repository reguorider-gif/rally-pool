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
