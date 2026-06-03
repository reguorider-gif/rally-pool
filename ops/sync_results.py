#!/usr/bin/env python3
"""
P10.0 sync_results — fetch match results and write snapshot.

Usage:
  python3 ops/sync_results.py --date 2026-06-03
  python3 ops/sync_results.py --date 2026-06-03 --dry-run
  python3 ops/sync_results.py --date 2026-06-03 --provider legacy_seed
"""

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # pool-app/
DATA_DIR = BASE_DIR / "data" / "pool"

sys.path.insert(0, str(BASE_DIR))

from ops.providers.legacy_seed_provider import LegacySeedProvider

PROVIDERS = {
    "legacy_seed": LegacySeedProvider(),
}


def sync_results(date: str, provider_name: str = "legacy_seed", dry_run: bool = False):
    provider = PROVIDERS.get(provider_name)
    if not provider:
        print(f"Unknown provider: {provider_name}", file=sys.stderr)
        sys.exit(1)

    data = provider.fetch_results(date)
    results = data.get("results", [])
    summary = data.get("summary", {})

    print(f"sync_results")
    print(f"date:     {date}")
    print(f"provider: {provider_name}")
    print(f"results:  {len(results)}")
    print(f"finished: {summary.get('finished', 0)}")
    print(f"missing_or_not_finished: {summary.get('missing_or_not_finished', 0)}")

    if dry_run:
        print("dry_run:  true")
        print("no files written")
        return

    # Write results
    out_dir = DATA_DIR / "match_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written:  {out_path.relative_to(BASE_DIR)}")
    print(f"dry_run:  false")


def main():
    parser = argparse.ArgumentParser(description="P10.0 Match results sync")
    parser.add_argument("--date", default="2026-06-03", help="Sync date (YYYY-MM-DD)")
    parser.add_argument("--provider", default="legacy_seed", help="Provider name")
    parser.add_argument("--dry-run", action="store_true", help="Print only, no writes")
    args = parser.parse_args()

    sync_results(args.date, args.provider, args.dry_run)


if __name__ == "__main__":
    main()
