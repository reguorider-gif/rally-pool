"""
P13.0A - 真实赔率源 smoke test。

读取 THE_ODDS_API_KEY 环境变量，调用 The Odds API 并生成 provider smoke 报告。
如果 key 未配置，生成 BLOCKED_PROVIDER_NOT_CONFIGURED 报告，不报错。
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
PROVIDER_SMOKE_DIR = DATA_DIR / "provider_smoke"
PROVIDER_SMOKE_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

from ops.sync_odds_snapshots import build_snapshot, load_matches

# ---- provider 配置 ----
PROVIDERS = {
    "the_odds_api": {
        "env_var": "THE_ODDS_API_KEY",
        "api_base": "https://api.the-odds-api.com/v4",
        "doc_url": "https://the-odds-api.com/",
        "endpoints": {
            "sports": "/sports",
            "odds": "/sports/{sport_key}/odds",
        },
    },
}


def build_blocked_report(round_id: str, date: str, provider: str = "the_odds_api") -> dict:
    """生成 BLOCKED_PROVIDER_NOT_CONFIGURED 报告。"""
    return {
        "version": "p13.0",
        "round_id": round_id,
        "date": date,
        "status": "BLOCKED_PROVIDER_NOT_CONFIGURED",
        "summary": {
            "provider": provider,
            "configured": False,
            "provider_responded": None,
            "matched_internal_matches": 0,
            "valid_odds_rows": 0,
            "coverage_status": "real_odds_provider_not_configured",
        },
        "blocks": [],
        "warnings": [
            f"{PROVIDERS[provider]['env_var']} is not set"
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_provider_smoke(
    round_id: str,
    date: str,
    provider: str = "the_odds_api",
    snapshot_label: str = "T-1h",
    markets: list = None,
    save_raw: bool = False,
    verbose: bool = False,
) -> dict:
    """运行真实赔率源 smoke test。"""
    if markets is None:
        markets = ["moneyline", "handicap", "total_goals"]

    api_key = os.environ.get("THE_ODDS_API_KEY")
    if not api_key:
        report = build_blocked_report(round_id, date, provider)
        _save_report(report, round_id, date)
        return report

    try:
        matches = load_matches()
        snapshot = build_snapshot(
            date=date,
            snapshot_label=snapshot_label,
            provider_name=provider,
            markets=markets,
            matches=matches,
        )
    except Exception as exc:
        report = {
            "version": "p13.0",
            "round_id": round_id,
            "date": date,
            "status": "FAILED_PROVIDER_SMOKE",
            "summary": {
                "provider": provider,
                "configured": True,
                "provider_responded": False,
                "matched_internal_matches": 0,
                "valid_odds_rows": 0,
                "coverage_status": "real_odds_provider_smoke_failed",
            },
            "blocks": [],
            "warnings": [f"provider smoke failed: {exc}"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_report(report, round_id, date)
        return report

    summary = snapshot.get("summary", {})
    provider_responded = bool(summary.get("provider_responded"))
    valid_odds_rows = int(summary.get("valid_odds_rows") or 0)
    coverage_status = summary.get("coverage_status", "unknown")

    if valid_odds_rows > 0:
        status = "PASS_REAL_PROVIDER_HAS_VALID_ODDS"
        warnings = []
    elif provider_responded:
        status = "PASS_REAL_PROVIDER_RESPONDED_NO_MATCH_COVERAGE"
        warnings = ["provider responded but no internal match coverage was found"]
    else:
        status = "WARN_REAL_PROVIDER_NO_COVERAGE"
        warnings = ["provider configured but no covered odds rows were returned"]

    report = {
        "version": "p13.0",
        "round_id": round_id,
        "date": date,
        "status": status,
        "summary": {
            "provider": provider,
            "configured": True,
            "provider_responded": provider_responded,
            "matched_internal_matches": summary.get("matched_internal_matches", 0),
            "valid_odds_rows": valid_odds_rows,
            "coverage_status": coverage_status,
            "odds_rows": summary.get("odds_rows", 0),
            "missing_market_coverage": summary.get("missing_market_coverage", 0),
            "match_mapping_failed": summary.get("match_mapping_failed", 0),
            "markets_requested": summary.get("markets_requested", markets),
        },
        "blocks": [],
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if save_raw:
        raw_dir = PROVIDER_SMOKE_DIR / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{round_id}_{date}_{provider}.json"
        raw_path.write_text(
            json.dumps(
                {
                    "note": "API key is not stored in this file.",
                    "snapshot": snapshot,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        report["raw_snapshot_path"] = str(raw_path.relative_to(ROOT))

    _save_report(report, round_id, date)
    return report


def _save_report(report: dict, round_id: str, date: str):
    """保存 provider smoke 报告。"""
    out_path = PROVIDER_SMOKE_DIR / f"{round_id}_{date}.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if os.environ.get("VERBOSE") or False:
        print(f"[run_real_provider_smoke] Wrote {out_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="P13.0A 真实赔率源 smoke test")
    parser.add_argument("--round", required=True, help="round id, e.g. run-6")
    parser.add_argument("--date", required=True, help="date, e.g. 2026-06-03")
    parser.add_argument("--provider", default="the_odds_api", help="provider name")
    parser.add_argument("--snapshot-label", default="T-1h", help="snapshot label")
    parser.add_argument("--markets", default="moneyline,handicap,total_goals", help="comma-separated markets")
    parser.add_argument("--save-raw", action="store_true", help="save raw API response")
    parser.add_argument("--verbose", action="store_true", help="verbose output")
    args = parser.parse_args()

    if args.verbose:
        os.environ["VERBOSE"] = "1"

    markets = [m.strip() for m in args.markets.split(",") if m.strip()]

    if not os.environ.get("THE_ODDS_API_KEY"):
        print(
            f"[run_real_provider_smoke] WARNING: {PROVIDERS[args.provider]['env_var']} is not set.\n"
            f"  action: export {PROVIDERS[args.provider]['env_var']}=<your_key>",
            file=sys.stderr,
        )

    report = run_provider_smoke(
        round_id=args.round,
        date=args.date,
        provider=args.provider,
        snapshot_label=args.snapshot_label,
        markets=markets,
        save_raw=args.save_raw,
        verbose=args.verbose,
    )

    out_path = PROVIDER_SMOKE_DIR / f"{args.round}_{args.date}.json"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[run_real_provider_smoke] Report saved to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
