#!/usr/bin/env python3
"""
ops/check_ops_readiness.py
P12.2 新增：检查 AI Judge 预测池的运维就绪状态。

功能：
1. 检查 GitHub workflow / Vercel cron / 生产文档 是否存在
2. 检查最新 pipeline / daily report 状态
3. 检查已知残留是否被记录
4. 检查前端和后端是否包含关键 API 路径
5. 输出人类可读报告 + JSON（写到 data/pool/ops_readiness/latest.json）

用法：
  python3 ops/check_ops_readiness.py
  python3 ops/check_ops_readiness.py --json
"""

from pathlib import Path
import json
import sys
import argparse
from datetime import datetime, timezone

# ── 路径配置 ────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "pool"
OUTPUT_DIR  = DATA_DIR / "ops_readiness"
OUTPUT_FILE = OUTPUT_DIR / "latest.json"

# ── 检查项定义 ──────────────────────────────────────────────────────────────

CHECKS = [
    # (id, description, check_fn)
    ("gh_workflow_exists",       "GitHub Actions workflow file exists",                         None),
    ("vercel_cron_config_exists","Vercel cron config (vercel.json) exists",                  None),
    ("prod_docs_exist",         "Production docs (runbook/alerting/incident/checklist) exist", None),
    ("latest_pipeline_exists",   "Latest pipeline run file exists",                            None),
    ("pipeline_final_status_ok", "Latest pipeline final_status in allowed states",             None),
    ("latest_daily_report_exists","Latest daily report file exists",                          None),
    ("health_check_can_pass",    "check_pool_data_health.py can PASS",                      None),
    ("known_residuals_documented","Known residuals (remote 404 / waiting / manual_stub) documented", None),
    ("frontend_has_scheduler",   "Frontend has /api/cron/pipeline-status reference",         None),
    ("alerting_docs_exist",     "Alerting policy doc exists",                               None),
]

ALLOWED_FINAL_STATUSES = {"pass", "pass_with_warnings", "failed", "blocked"}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _read_json(relative_path, default=None):
    full = DATA_DIR / relative_path
    if not full.exists():
        return default
    try:
        return json.loads(full.read_text(encoding="utf-8"))
    except Exception:
        return default


def run_check(check_health_too=False):
    """
    执行全部检查，返回 (results_list, warnings, blockers, next_actions)
    """
    results = []
    warnings = []
    blockers = []
    next_actions = []

    # ── 1. GitHub workflow file exists ────────────────────────────────────
    wf_path = ROOT / ".github" / "workflows" / "daily-pool-pipeline.yml"
    ok = wf_path.exists()
    results.append({
        "id": "gh_workflow_exists",
        "description": "GitHub Actions workflow file exists",
        "status": "pass" if ok else "fail",
        "detail": str(wf_path) if ok else "missing",
    })
    if not ok:
        blockers.append("GitHub Actions workflow file (.github/workflows/daily-pool-pipeline.yml) is missing")
        next_actions.append("Create .github/workflows/daily-pool-pipeline.yml")

    # ── 2. Vercel cron config exists ──────────────────────────────────────
    vj_path = ROOT / "vercel.json"
    ok = vj_path.exists()
    detail = "exists"
    if ok:
        try:
            vj = json.loads(vj_path.read_text(encoding="utf-8"))
            has_crons = bool(vj.get("crons"))
            detail = f"exists, crons={'present' if has_crons else 'MISSING'}"
            if not has_crons:
                ok = False
        except Exception:
            detail = "exists but JSON parse failed"
            ok = False
    results.append({
        "id": "vercel_cron_config_exists",
        "description": "Vercel cron config (vercel.json) exists",
        "status": "pass" if ok else "fail",
        "detail": detail,
    })
    if not ok:
        blockers.append("vercel.json missing or does not contain crons config")
        next_actions.append("Add crons config to vercel.json")

    # ── 3. Production docs exist ──────────────────────────────────────────
    docs = [
        ROOT / "docs" / "PRODUCTION_RUNBOOK.md",
        ROOT / "docs" / "ALERTING_POLICY.md",
        ROOT / "docs" / "INCIDENT_PLAYBOOK.md",
        ROOT / "docs" / "OPERATIONS_CHECKLIST.md",
    ]
    missing_docs = [d for d in docs if not d.exists()]
    all_exist = len(missing_docs) == 0
    results.append({
        "id": "prod_docs_exist",
        "description": "Production docs (runbook/alerting/incident/checklist) exist",
        "status": "pass" if all_exist else "fail",
        "detail": f"{len(docs) - len(missing_docs)}/{len(docs)} docs present",
    })
    for md in missing_docs:
        blockers.append(f"Production doc missing: {md.name}")
        next_actions.append(f"Create {md.name}")

    # ── 4. Latest pipeline exists ─────────────────────────────────────────
    pr_dir = DATA_DIR / "pipeline_runs"
    latest_pr = None
    if pr_dir.exists():
        json_files = sorted(pr_dir.glob("*.json"), reverse=True)
        if json_files:
            latest_pr = json_files[0]
    ok = latest_pr is not None
    results.append({
        "id": "latest_pipeline_exists",
        "description": "Latest pipeline run file exists",
        "status": "pass" if ok else "fail",
        "detail": latest_pr.name if ok else "no pipeline_runs/*.json found",
    })
    if not ok:
        warnings.append("No pipeline run files found in data/pool/pipeline_runs/")
        next_actions.append("Run ops/run_daily_pool_pipeline.py to generate a pipeline run")

    # ── 5. Pipeline final_status in allowed states ────────────────────────
    final_status_ok = False
    final_status_val = None
    if latest_pr:
        try:
            pr_data = json.loads(latest_pr.read_text(encoding="utf-8"))
            final_status_val = pr_data.get("final_status", "")
            final_status_ok = final_status_val in ALLOWED_FINAL_STATUSES
        except Exception as e:
            final_status_val = f"parse_error: {e}"
    results.append({
        "id": "pipeline_final_status_ok",
        "description": "Latest pipeline final_status in allowed states",
        "status": "pass" if final_status_ok else "fail",
        "detail": final_status_val or "N/A",
    })
    if not final_status_ok and latest_pr:
        blockers.append(f"Latest pipeline final_status='{final_status_val}' is not in {ALLOWED_FINAL_STATUSES}")
        next_actions.append("Investigate latest pipeline run failure")

    # ── 6. Latest daily report exists ─────────────────────────────────────
    dr_dir = DATA_DIR / "daily_reports"
    latest_dr = None
    if dr_dir.exists():
        json_files = sorted(dr_dir.glob("*.json"), reverse=True)
        if json_files:
            latest_dr = json_files[0]
    ok = latest_dr is not None
    results.append({
        "id": "latest_daily_report_exists",
        "description": "Latest daily report file exists",
        "status": "pass" if ok else "fail",
        "detail": latest_dr.name if ok else "no daily_reports/*.json found",
    })
    if not ok:
        warnings.append("No daily report files found in data/pool/daily_reports/")
        next_actions.append("Run ops/generate_daily_pool_report.py to generate a daily report")

    # ── 7. Health check can pass ─────────────────────────────────────────
    health_pass = False
    health_detail = "not_run"
    try:
        # Import and run the health check as a function call
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ROOT / "ops" / "check_pool_data_health.py")],
            capture_output=True, text=True, timeout=60
        )
        health_detail = f"exit_code={result.returncode}"
        health_pass = result.returncode == 0
        if not health_pass:
            health_detail += f", stderr_tail={result.stderr[-200:] if result.stderr else 'empty'}"
    except Exception as e:
        health_detail = f"exception: {e}"
    results.append({
        "id": "health_check_can_pass",
        "description": "check_pool_data_health.py can PASS",
        "status": "pass" if health_pass else "fail",
        "detail": health_detail,
    })
    if not health_pass:
        blockers.append("check_pool_data_health.py did not PASS")
        next_actions.append("Run python3 ops/check_pool_data_health.py and fix errors")

    # ── 8. Known residuals documented ────────────────────────────────────
    residuals_doc = ROOT / "docs" / "PRODUCTION_RUNBOOK.md"
    residuals_found = []
    if residuals_doc.exists():
        txt = residuals_doc.read_text(encoding="utf-8")
        for keyword in ["GitHub remote 404", "waiting_for_manual_ingest", "manual_stub"]:
            if keyword in txt:
                residuals_found.append(keyword)
    ok = len(residuals_found) >= 2  # at least 2 of 3 documented
    results.append({
        "id": "known_residuals_documented",
        "description": "Known residuals (remote 404 / waiting / manual_stub) documented",
        "status": "pass" if ok else "warn",
        "detail": f"documented: {residuals_found}",
    })
    if not ok:
        warnings.append("Known residuals may not be fully documented in PRODUCTION_RUNBOOK.md")
        next_actions.append("Update PRODUCTION_RUNBOOK.md with known residuals")

    # ── 9. Frontend has scheduler block ──────────────────────────────────
    html_path = ROOT / "html" / "index.html"
    ok = False
    if html_path.exists():
        txt = html_path.read_text(encoding="utf-8")
        ok = "/api/cron/pipeline-status" in txt and "Scheduler" in txt
    results.append({
        "id": "frontend_has_scheduler",
        "description": "Frontend has /api/cron/pipeline-status reference",
        "status": "pass" if ok else "fail",
        "detail": "found" if ok else "missing reference in html/index.html",
    })
    if not ok:
        warnings.append("Frontend (html/index.html) does not reference /api/cron/pipeline-status")
        next_actions.append("Update html/index.html to include Scheduler / Deployment section")

    # ── 10. Alerting docs exist ──────────────────────────────────────────
    alerting_doc = ROOT / "docs" / "ALERTING_POLICY.md"
    incident_doc = ROOT / "docs" / "INCIDENT_PLAYBOOK.md"
    ok = alerting_doc.exists() and incident_doc.exists()
    results.append({
        "id": "alerting_docs_exist",
        "description": "Alerting policy + incident playbook exist",
        "status": "pass" if ok else "fail",
        "detail": f"alerting={'ok' if alerting_doc.exists() else 'missing'}, incident={'ok' if incident_doc.exists() else 'missing'}",
    })
    if not ok:
        blockers.append("Alerting policy or incident playbook is missing")
        next_actions.append("Create docs/ALERTING_POLICY.md and docs/INCIDENT_PLAYBOOK.md")

    # ── Determine overall_status ──────────────────────────────────────────
    if blockers:
        overall_status = "blocked"
    elif warnings:
        overall_status = "ready_with_warnings"
    else:
        overall_status = "ready"

    return results, warnings, blockers, next_actions, overall_status


def generate_output(results, warnings, blockers, next_actions, overall_status, as_json=False):
    """Generate human-readable or JSON output."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "version":         "p12.2",
        "generated_at":    _now_iso(),
        "overall_status":   overall_status,
        "checks":           results,
        "warnings":         warnings,
        "blockers":         blockers,
        "next_actions":     next_actions,
    }

    # Always write JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[check_ops_readiness] Wrote {OUTPUT_FILE}")

    if as_json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # Human-readable
        print("\n=== AI Judge Pool Ops Readiness ===")
        print(f"  Generated at : {output['generated_at']}")
        print(f"  Overall status: {output['overall_status'].upper()}")
        print()
        print("  Checks:")
        for c in results:
            icon = "✅" if c['status'] == 'pass' else ("⚠️" if c['status'] == 'warn' else "❌")
            print(f"    {icon} [{c['id']}] {c['description']}")
            print(f"       → {c['detail']}")
        if warnings:
            print()
            print("  Warnings:")
            for w in warnings:
                print(f"    ⚠️  {w}")
        if blockers:
            print()
            print("  Blockers:")
            for b in blockers:
                print(f"    ❌ {b}")
        if next_actions:
            print()
            print("  Next Actions:")
            for i, a in enumerate(next_actions, 1):
                print(f"    {i}. {a}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Check AI Judge Pool ops readiness")
    parser.add_argument("--json", action="store_true", help="Output as JSON only")
    args = parser.parse_args()

    results, warnings, blockers, next_actions, overall_status = run_check()
    generate_output(results, warnings, blockers, next_actions, overall_status, as_json=args.json)

    # Exit code: 0 = ready/ready_with_warnings, 1 = blocked
    sys.exit(0 if overall_status != "blocked" else 1)


if __name__ == "__main__":
    main()
