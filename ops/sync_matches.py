#!/usr/bin/env python3
"""
P10.0 sync_matches — fetch match schedule and write snapshot.

Usage:
  python3 ops/sync_matches.py --date 2026-06-03 --days 14
  python3 ops/sync_matches.py --date 2026-06-03 --days 14 --dry-run
  python3 ops/sync_matches.py --date 2026-06-03 --days 14 --provider legacy_seed
"""

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # pool-app/
DATA_DIR = BASE_DIR / "data" / "pool"

# Ensure ops/ is importable
sys.path.insert(0, str(BASE_DIR))

from ops.providers.legacy_seed_provider import LegacySeedProvider

PROVIDERS = {
    "legacy_seed": LegacySeedProvider(),
}


def sync_matches(date: str, days: int, provider_name: str = "legacy_seed", dry_run: bool = False):
    provider = PROVIDERS.get(provider_name)
    if not provider:
        print(f"Unknown provider: {provider_name}", file=sys.stderr)
        sys.exit(1)

    data = provider.fetch_matches(date, days)
    matches = data.get("matches", [])

    print(f"sync_matches")
    print(f"date:     {date}")
    print(f"days:     {days}")
    print(f"provider: {provider_name}")
    print(f"matches:  {len(matches)}")

    if dry_run:
        print("dry_run:  true")
        print("no files written")
        return

    # Write snapshot
    snap_dir = DATA_DIR / "matches" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"{date}.json"
    snap_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written:  {snap_path.relative_to(BASE_DIR)}")

    # Update current.json (preserve existing match_ids, update fields if present in snapshot)
    current_path = DATA_DIR / "matches" / "current.json"
    if current_path.exists():
        try:
            current = json.loads(current_path.read_text(encoding="utf-8"))
        except Exception:
            current = {"version": "p10.0", "updated_at": "", "matches": []}

        current["version"] = "p10.0"
        current["updated_at"] = data.get("fetched_at", "")
        # Build lookup from current
        current_by_id = {m.get("match_id"): m for m in current.get("matches", [])}
        for snap_m in matches:
            mid = snap_m.get("match_id")
            if mid in current_by_id:
                # Update only metadata fields, preserve original structure
                existing = current_by_id[mid]
                existing["provider"] = snap_m.get("provider", existing.get("provider", ""))
                existing["source_url"] = snap_m.get("source_url", existing.get("source_url", ""))
                existing["fetched_at"] = snap_m.get("fetched_at", existing.get("fetched_at", ""))
                existing["confidence"] = snap_m.get("confidence", existing.get("confidence", 0.5))
                if snap_m.get("kickoff_at"):
                    existing["kickoff_at"] = snap_m.get("kickoff_at")
                existing["status"] = snap_m.get("status", existing.get("status", "scheduled"))
            else:
                current["matches"].append(snap_m)
        current_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"updated_current: true")
    else:
        # No current.json — write snapshot as current
        current_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"current_initialized: true (no prior current.json)")

    print(f"dry_run:  false")


def main():
    parser = argparse.ArgumentParser(description="P10.0 Match schedule sync")
    parser.add_argument("--date", default="2026-06-03", help="Sync date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=14, help="Match window in days")
    parser.add_argument("--provider", default="legacy_seed", help="Provider name")
    parser.add_argument("--dry-run", action="store_true", help="Print only, no writes")
    args = parser.parse_args()

    sync_matches(args.date, args.days, args.provider, args.dry_run)


if __name__ == "__main__":
    main()
