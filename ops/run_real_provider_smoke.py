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

    # TODO: P13.2A 实现真实 API 调用
    # 当前先返回 BLOCKED，不伪造数据
    report = build_blocked_report(round_id, date, provider)
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
