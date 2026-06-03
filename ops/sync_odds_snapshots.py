#!/usr/bin/env python3
"""
P10.1 sync_odds_snapshots — fetch odds snapshots and write to data/pool/odds_snapshots/.

Usage:
  python3 ops/sync_odds_snapshots.py --date 2026-06-03 --snapshot-label T-1h --provider manual_stub
  python3 ops/sync_odds_snapshots.py --date 2026-06-03 --snapshot-label T-1h --provider the_odds_api
  python3 ops/sync_odds_snapshots.py --date 2026-06-03 --snapshot-label T-1h --dry-run
  python3 ops/sync_odds_snapshots.py --date 2026-06-03 --snapshot-label T-1h --markets moneyline,handicap,total_goals
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # pool-app/
DATA_DIR = BASE_DIR / "data" / "pool"
SNAP_DIR = DATA_DIR / "odds_snapshots"
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


def load_existing_snapshot(date: str, snapshot_label: str) -> dict | None:
    """Load existing snapshot if present."""
    p = SNAP_DIR / f"{date}_{snapshot_label}.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def build_snapshot(date: str, snapshot_label: str, provider_name: str,
                   markets: list, matches: list, dry_run: bool) -> dict:
    """Build the odds snapshot dict."""
    provider = PROVIDERS.get(provider_name)
    if not provider:
        print(f"  [error] Unknown provider: {provider_name}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch odds from provider
    odds_rows = provider.fetch_odds(date, snapshot_label, matches, markets)

    # Count stats
    # missing_market_coverage = unique (match_id, market) pairs with no valid odds
    # For manual_stub: all (match, market) pairs have missing coverage
    odds_count = 0
    valid_odds_count = 0
    missing_coverage_pairs = set()
    match_mapping_failed = 0
    provider_unavailable = False

    for row in odds_rows:
        odds_count += 1
        mid = row.get("match_id")
        mkt = row.get("market")
        s = row.get("status", "")
        if s == "match_mapping_failed":
            match_mapping_failed += 1
        elif s == "provider_unavailable":
            provider_unavailable = True
        odds_val = row.get("odds")
        if odds_val is not None and odds_val > 0:
            valid_odds_count += 1
        else:
            if mid and mkt:
                missing_coverage_pairs.add((mid, mkt))

    if not provider.is_available() if hasattr(provider, "is_available") else False:
        provider_unavailable = True

    snapshot = {
        "version":                "p10.1",
        "date":                   date,
        "snapshot_label":         snapshot_label,
        "provider":               provider_name,
        "fetched_at":             now,
        "source_policy":          "manual_stub_no_external_fetch" if provider_name == "manual_stub" else "the_odds_api_live",
        "summary": {
            "matches_total":          len(matches),
            "markets_requested":     markets,
            "odds_rows":             odds_count,
            "valid_odds_rows":        valid_odds_count,
            "missing_market_coverage": len(missing_coverage_pairs),
            "match_mapping_failed":   match_mapping_failed,
            "provider_unavailable":   provider_unavailable,
        },
        "odds": odds_rows,
    }
    return snapshot


def update_index(date: str, snapshot_label: str, provider_name: str,
                 snapshot_data: dict):
    """Update or create odds_snapshots/index.json."""
    index = {"version": "p10.1", "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "snapshots": []}

    if INDEX_PATH.exists():
        with open(INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)

    # Remove existing entry for this date+label if present
    index["snapshots"] = [
        s for s in index.get("snapshots", [])
        if not (s.get("date") == date and s.get("snapshot_label") == snapshot_label)
    ]

    summary = snapshot_data.get("summary", {})
    index["snapshots"].append({
        "date":                     date,
        "snapshot_label":           snapshot_label,
        "provider":                 provider_name,
        "path":                     f"data/pool/odds_snapshots/{date}_{snapshot_label}.json",
        "odds_rows":                summary.get("odds_rows", 0),
        "valid_odds_rows":          summary.get("valid_odds_rows", 0),
        "missing_market_coverage":  summary.get("missing_market_coverage", 0),
    })
    index["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return index


def sync_odds(date: str, snapshot_label: str, provider_name: str,
              markets: list, dry_run: bool, verbose: bool):
    """Main sync logic."""
    matches = load_matches()
    print(f"sync_odds_snapshots")
    print(f"  date:           {date}")
    print(f"  snapshot_label: {snapshot_label}")
    print(f"  provider:       {provider_name}")
    print(f"  matches:        {len(matches)}")
    print(f"  markets:        {','.join(markets)}")
    print(f"  dry_run:        {dry_run}")

    snapshot = build_snapshot(date, snapshot_label, provider_name, markets, matches, dry_run)

    odds_rows = snapshot.get("odds", [])
    summary = snapshot.get("summary", {})
    print(f"  odds_rows:      {len(odds_rows)}")
    print(f"  valid_odds:    {summary.get('valid_odds_rows', 0)}")
    print(f"  missing_cov:   {summary.get('missing_market_coverage', 0)}")

    if dry_run:
        print("  [dry-run] no files written")
        return

    # Write snapshot
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    snap_path = SNAP_DIR / f"{date}_{snapshot_label}.json"
    snap_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  [write] {snap_path.relative_to(BASE_DIR)}")

    # Update index
    index = update_index(date, snapshot_label, provider_name, snapshot)
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  [write] {INDEX_PATH.relative_to(BASE_DIR)}")

    if verbose:
        print(f"\n  Snapshot summary:")
        print(f"    matches_total:          {summary.get('matches_total')}")
        print(f"    markets_requested:     {summary.get('markets_requested')}")
        print(f"    odds_rows:             {summary.get('odds_rows')}")
        print(f"    valid_odds_rows:       {summary.get('valid_odds_rows')}")
        print(f"    missing_market_coverage: {summary.get('missing_market_coverage')}")
        print(f"    match_mapping_failed:  {summary.get('match_mapping_failed')}")
        print(f"    provider_unavailable:  {summary.get('provider_unavailable')}")


def main():
    parser = argparse.ArgumentParser(description="P10.1 Odds snapshots sync")
    parser.add_argument("--date",           default="2026-06-03", help="Snapshot date (YYYY-MM-DD)")
    parser.add_argument("--snapshot-label", default="T-1h",        help="Snapshot label (T-24h, T-1h, T-15m, ...)")
    parser.add_argument("--provider",       default="manual_stub",   help="Provider name (manual_stub | the_odds_api)")
    parser.add_argument("--markets",        default=",".join(DEFAULT_MARKETS), help="Comma-separated markets")
    parser.add_argument("--dry-run",       action="store_true",     help="Print only, no writes")
    parser.add_argument("--verbose",       action="store_true",     help="Verbose output")
    args = parser.parse_args()

    markets = [m.strip() for m in args.markets.split(",") if m.strip()]
    sync_odds(args.date, args.snapshot_label, args.provider, markets, args.dry_run, args.verbose)


if __name__ == "__main__":
    main()
