#!/usr/bin/env python3
"""
P10.1 / P13.0 sync_odds_snapshots — fetch odds snapshots and write to data/pool/odds_snapshots/.

Usage:
  # manual_stub (backward compat)
  python3 ops/sync_odds_snapshots.py --date 2026-06-03 --snapshot-label T-1h --provider manual_stub

  # the_odds_api (real provider)
  python3 ops/sync_odds_snapshots.py --date 2026-06-03 --snapshot-label T-1h --provider the_odds_api

  # real provider with strict mode
  THE_ODDS_API_KEY=... python3 ops/sync_odds_snapshots.py \\
    --date 2026-06-03 --snapshot-label T-1h --provider the_odds_api \\
    --markets moneyline,handicap,total_goals --save-raw --strict-real-provider --verbose

  # dry run
  python3 ops/sync_odds_snapshots.py --date 2026-06-03 --snapshot-label T-1h --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # pool-app/
DATA_DIR = BASE_DIR / "data" / "pool"
SNAP_DIR = DATA_DIR / "odds_snapshots"
RAW_DIR = SNAP_DIR / "raw"
INDEX_PATH = SNAP_DIR / "index.json"

sys.path.insert(0, str(BASE_DIR))

from ops.providers.manual_odds_provider import ManualOddsProvider
from ops.providers.the_odds_api_provider import TheOddsApiProvider

PROVIDERS = {
    "manual_stub": ManualOddsProvider(),
    "the_odds_api": TheOddsApiProvider(),
}

DEFAULT_MARKETS = ["moneyline", "handicap", "total_goals"]


def load_matches() -> list:
    """Load matches from data/pool/matches/current.json."""
    p = DATA_DIR / "matches" / "current.json"
    if not p.exists():
        print(f"  [error] matches/current.json not found", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("matches", [])


def _snapshot_filename(date: str, snapshot_label: str, provider_name: str) -> str:
    """
    生成快照文件名。
    - manual_stub: {date}_{label}.json（向后兼容）
    - 其他 provider: {date}_{label}_{provider}.json（不覆盖 manual_stub）
    """
    if provider_name == "manual_stub":
        return f"{date}_{snapshot_label}.json"
    return f"{date}_{snapshot_label}_{provider_name}.json"


def _coverage_status(summary: dict, provider_name: str) -> str:
    """根据 summary 判定 coverage_status（5态检测）。"""
    provider_unavail = summary.get("provider_unavailable", False)
    valid = summary.get("valid_odds_rows", 0)
    total = summary.get("odds_rows", 0)

    if provider_unavail:
        return "real_odds_provider_not_configured"
    if total > 0 and valid == 0:
        if provider_name == "manual_stub":
            return "odds_snapshots_present_but_missing_market_coverage"
        else:
            return "real_odds_provider_responded_but_no_match_coverage"
    if valid > 0:
        return "real_odds_provider_has_valid_odds"
    return "missing_odds_snapshots"


def build_snapshot(date: str, snapshot_label: str, provider_name: str,
                   markets: list, matches: list) -> dict:
    """Build the odds snapshot dict."""
    provider = PROVIDERS.get(provider_name)
    if not provider:
        print(f"  [error] Unknown provider: {provider_name}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch odds from provider
    odds_rows = provider.fetch_odds(date, snapshot_label, matches, markets)

    # Count stats
    odds_count = 0
    valid_odds_count = 0
    missing_coverage_pairs = set()
    match_mapping_failed = 0
    provider_unavailable = False
    provider_responded = False

    for row in odds_rows:
        odds_count += 1
        mid = row.get("match_id")
        mkt = row.get("market")
        s = row.get("status", "")
        if s == "match_mapping_failed":
            match_mapping_failed += 1
        elif s == "provider_unavailable":
            provider_unavailable = True
        elif s not in ("missing_market_coverage", "market_not_supported", "manual_review"):
            provider_responded = True
        odds_val = row.get("odds")
        if odds_val is not None and odds_val > 0:
            valid_odds_count += 1
        else:
            if mid and mkt:
                missing_coverage_pairs.add((mid, mkt))

    if hasattr(provider, "is_available") and not provider.is_available():
        provider_unavailable = True

    # Determine source policy
    if provider_name == "manual_stub":
        source_policy = "manual_stub_no_external_fetch"
    elif provider_unavailable:
        source_policy = "the_odds_api_unavailable"
    elif provider_responded:
        source_policy = "the_odds_api_live"
    else:
        source_policy = "the_odds_api_no_match_coverage"

    summary = {
        "matches_total":           len(matches),
        "markets_requested":       markets,
        "odds_rows":               odds_count,
        "valid_odds_rows":         valid_odds_count,
        "missing_market_coverage":  len(missing_coverage_pairs),
        "match_mapping_failed":    match_mapping_failed,
        "provider_unavailable":    provider_unavailable,
        "provider_responded":      provider_responded,
        "matched_internal_matches": len(set(
            r.get("match_id") for r in odds_rows
            if r.get("match_id") and r.get("status", "") not in (
                "match_mapping_failed", "provider_unavailable"
            )
        )),
    }

    coverage = _coverage_status(summary, provider_name)
    summary["coverage_status"] = coverage

    snapshot = {
        "version":        "p13.0",
        "date":           date,
        "snapshot_label": snapshot_label,
        "provider":       provider_name,
        "fetched_at":     now,
        "source_policy":  source_policy,
        "summary":        summary,
        "odds":           odds_rows,
    }
    return snapshot


def save_raw_response(date: str, snapshot_label: str, provider_name: str,
                      snapshot: dict):
    """Save raw provider response (API key already redacted by provider)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_filename = _snapshot_filename(date, snapshot_label, provider_name)
    raw_path = RAW_DIR / raw_filename
    raw_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  [raw] {raw_path.relative_to(BASE_DIR)}")


def update_index(date: str, snapshot_label: str, provider_name: str,
                 snapshot_data: dict) -> dict:
    """Update or create odds_snapshots/index.json（provider-aware）。"""
    index = {
        "version": "p13.0",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshots": [],
    }

    if INDEX_PATH.exists():
        with open(INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)

    # Remove existing entries: same date+label+provider
    index["snapshots"] = [
        s for s in index.get("snapshots", [])
        if not (
            s.get("date") == date
            and s.get("snapshot_label") == snapshot_label
            and s.get("provider") == provider_name
        )
    ]

    summary = snapshot_data.get("summary", {})
    filename = _snapshot_filename(date, snapshot_label, provider_name)

    index["snapshots"].append({
        "date":                     date,
        "snapshot_label":           snapshot_label,
        "provider":                 provider_name,
        "path":                     f"data/pool/odds_snapshots/{filename}",
        "odds_rows":                summary.get("odds_rows", 0),
        "valid_odds_rows":          summary.get("valid_odds_rows", 0),
        "missing_market_coverage":  summary.get("missing_market_coverage", 0),
        "coverage_status":          summary.get("coverage_status", "unknown"),
        "provider_unavailable":     summary.get("provider_unavailable", False),
        "provider_responded":       summary.get("provider_responded", False),
        "matched_internal_matches": summary.get("matched_internal_matches", 0),
    })
    index["version"] = "p13.0"
    index["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return index


def sync_odds(date: str, snapshot_label: str, provider_name: str,
              markets: list, dry_run: bool, verbose: bool,
              save_raw: bool = False, strict_real: bool = False):
    """Main sync logic."""
    # ── strict-real-provider 检查 ──
    if strict_real and provider_name != "manual_stub":
        provider = PROVIDERS.get(provider_name)
        if provider and not provider.is_available():
            print("  [error] --strict-real-provider enabled but API key missing", file=sys.stderr)
            print(f"  provider: {provider_name}", file=sys.stderr)
            print(f"  action: export THE_ODDS_API_KEY=<your_key>", file=sys.stderr)
            # 输出结构化错误
            error_result = {
                "version":        "p13.0",
                "generated_at":    datetime.now(timezone.utc).isoformat(),
                "provider":        provider_name,
                "status":          "BLOCKED_PROVIDER_NOT_CONFIGURED",
                "error":           "THE_ODDS_API_KEY is not set.",
                "exit_code":       2,
                "hint":            "export THE_ODDS_API_KEY=<your_key>",
            }
            print(json.dumps(error_result, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(2)

    matches = load_matches()
    print(f"sync_odds_snapshots  [p13.0]")
    print(f"  date:           {date}")
    print(f"  snapshot_label: {snapshot_label}")
    print(f"  provider:       {provider_name}")
    print(f"  matches:        {len(matches)}")
    print(f"  markets:        {','.join(markets)}")
    print(f"  dry_run:        {dry_run}")
    print(f"  save_raw:       {save_raw}")
    print(f"  strict_real:    {strict_real}")

    snapshot = build_snapshot(date, snapshot_label, provider_name, markets, matches)

    odds_rows = snapshot.get("odds", [])
    summary = snapshot.get("summary", {})
    coverage = summary.get("coverage_status", "unknown")

    print(f"  odds_rows:      {len(odds_rows)}")
    print(f"  valid_odds:     {summary.get('valid_odds_rows', 0)}")
    print(f"  missing_cov:    {summary.get('missing_market_coverage', 0)}")
    print(f"  coverage:       {coverage}")
    print(f"  provider_resp:  {summary.get('provider_responded', False)}")
    print(f"  matched_matches: {summary.get('matched_internal_matches', 0)}")

    if dry_run:
        print("  [dry-run] no files written")
        return

    # Write snapshot (provider-specific filename)
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    filename = _snapshot_filename(date, snapshot_label, provider_name)
    snap_path = SNAP_DIR / filename
    snap_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  [write] {snap_path.relative_to(BASE_DIR)}")

    # Save raw if requested
    if save_raw:
        save_raw_response(date, snapshot_label, provider_name, snapshot)

    # Update index
    index = update_index(date, snapshot_label, provider_name, snapshot)
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  [write] {INDEX_PATH.relative_to(BASE_DIR)}")

    if verbose:
        print(f"\n  Snapshot summary:")
        print(f"    matches_total:           {summary.get('matches_total')}")
        print(f"    markets_requested:       {summary.get('markets_requested')}")
        print(f"    odds_rows:               {summary.get('odds_rows')}")
        print(f"    valid_odds_rows:         {summary.get('valid_odds_rows')}")
        print(f"    missing_market_coverage: {summary.get('missing_market_coverage')}")
        print(f"    match_mapping_failed:    {summary.get('match_mapping_failed')}")
        print(f"    provider_unavailable:    {summary.get('provider_unavailable')}")
        print(f"    provider_responded:      {summary.get('provider_responded')}")
        print(f"    matched_internal_matches:{summary.get('matched_internal_matches')}")
        print(f"    coverage_status:         {coverage}")


def main():
    parser = argparse.ArgumentParser(description="P10.1 / P13.0 Odds snapshots sync")
    parser.add_argument("--date",            default="2026-06-03",
                        help="Snapshot date (YYYY-MM-DD)")
    parser.add_argument("--snapshot-label",  default="T-1h",
                        help="Snapshot label (T-24h, T-1h, T-15m, ...)")
    parser.add_argument("--provider",        default="manual_stub",
                        help="Provider name (manual_stub | the_odds_api)")
    parser.add_argument("--markets",         default=",".join(DEFAULT_MARKETS),
                        help="Comma-separated markets")
    parser.add_argument("--dry-run",         action="store_true",
                        help="Print only, no writes")
    parser.add_argument("--verbose",         action="store_true",
                        help="Verbose output")
    parser.add_argument("--save-raw",        action="store_true",
                        help="Save a copy of the raw odds snapshot to raw/ dir")
    parser.add_argument("--region",          default="us,uk,eu,au",
                        help="Comma-separated bookmaker regions (for the_odds_api)")
    parser.add_argument("--sport",           default="soccer",
                        help="Sport key (for the_odds_api)")
    parser.add_argument("--strict-real-provider", action="store_true",
                        help="If API key missing, exit non-zero with structured error")
    args = parser.parse_args()

    # Validate strict mode
    if args.strict_real_provider and args.provider == "manual_stub":
        print("  [warning] --strict-real-provider ignored for manual_stub", file=sys.stderr)

    markets = [m.strip() for m in args.markets.split(",") if m.strip()]
    sync_odds(
        date=args.date,
        snapshot_label=args.snapshot_label,
        provider_name=args.provider,
        markets=markets,
        dry_run=args.dry_run,
        verbose=args.verbose,
        save_raw=args.save_raw,
        strict_real=args.strict_real_provider,
    )


if __name__ == "__main__":
    main()
