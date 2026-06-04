#!/usr/bin/env python3
from __future__ import annotations
"""
P14.0 provider-covered eligible board.

Builds the only board that models are allowed to bet from. A bet can be
settlement-eligible only when it cites one of these rows by board_id or
odds_row_id.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "pool"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _snapshot_path(date: str, snapshot_label: str, provider: str) -> Path:
    if provider and provider != "manual_stub":
        return DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}_{provider}.json"
    return DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}.json"


def _valid_provider_row(row: dict, provider: str) -> bool:
    if not isinstance(row, dict):
        return False
    odds = row.get("odds")
    if not isinstance(odds, (int, float)) or odds <= 1:
        return False
    if row.get("status") not in ("ok", "valid", "", None):
        return False
    if provider == "manual_stub" or row.get("bookmaker_or_provider") == "fallback":
        return False
    if not row.get("snapshot_id"):
        return False
    if not row.get("match_id") or not row.get("market") or not row.get("selection"):
        return False
    return True


def build_eligible_board(round_id: str, date: str, snapshot_label: str = "T-1h",
                         provider: str = "the_odds_api") -> dict:
    matches = _load_json(DATA_DIR / "matches" / "current.json", default={}) or {}
    snapshot_path = _snapshot_path(date, snapshot_label, provider)
    snapshot = _load_json(snapshot_path, default={}) or {}
    match_map = {
        m.get("match_id"): m
        for m in matches.get("matches", [])
        if isinstance(m, dict) and m.get("match_id")
    }

    provider_snapshot_id = snapshot_path.stem
    items = []
    for row in snapshot.get("odds", []):
        if not _valid_provider_row(row, provider):
            continue
        match = match_map.get(row.get("match_id"))
        if not match:
            continue
        odds_row_id = row.get("snapshot_id")
        board_id = f"{round_id}:{odds_row_id}"
        items.append({
            "board_id": board_id,
            "provider": provider,
            "provider_snapshot_id": provider_snapshot_id,
            "odds_row_id": odds_row_id,
            "match_id": row.get("match_id"),
            "home_team": match.get("home_team"),
            "away_team": match.get("away_team"),
            "commence_time": match.get("kickoff_at") or match.get("commence_time"),
            "market": row.get("market"),
            "selection": row.get("selection"),
            "price": row.get("odds"),
            "last_update": row.get("fetched_at") or snapshot.get("fetched_at"),
            "bookmaker_or_provider": row.get("bookmaker_or_provider"),
            "valid_for_settlement": True,
        })

    items.sort(key=lambda x: (
        str(x.get("commence_time") or ""),
        str(x.get("match_id") or ""),
        str(x.get("market") or ""),
        str(x.get("selection") or ""),
        str(x.get("bookmaker_or_provider") or ""),
    ))
    markets = sorted({i.get("market") for i in items if i.get("market")})
    match_ids = sorted({i.get("match_id") for i in items if i.get("match_id")})
    return {
        "version": "p14.0",
        "round_id": round_id,
        "date": date,
        "snapshot_label": snapshot_label,
        "provider": provider,
        "provider_snapshot_id": provider_snapshot_id,
        "generated_at": _now_iso(),
        "summary": {
            "eligible_board_rows": len(items),
            "markets": markets,
            "matches_covered": len(match_ids),
            "match_ids": match_ids,
            "valid_for_settlement": bool(items),
        },
        "items": items,
    }


def write_eligible_board(board: dict) -> Path:
    round_id = board.get("round_id") or "run-unknown"
    out_path = DATA_DIR / "odds" / "eligible_board" / f"{round_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(board, f, ensure_ascii=False, indent=2)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate provider-covered eligible board")
    parser.add_argument("--round", required=True, dest="round_id")
    parser.add_argument("--date", required=True)
    parser.add_argument("--snapshot-label", default="T-1h")
    parser.add_argument("--provider", default="the_odds_api")
    args = parser.parse_args()

    board = build_eligible_board(
        round_id=args.round_id,
        date=args.date,
        snapshot_label=args.snapshot_label,
        provider=args.provider,
    )
    out_path = write_eligible_board(board)
    print("generate_eligible_board")
    print(f"  round_id: {args.round_id}")
    print(f"  provider: {args.provider}")
    print(f"  rows: {board.get('summary', {}).get('eligible_board_rows', 0)}")
    print(f"  markets: {', '.join(board.get('summary', {}).get('markets', []))}")
    print(f"  [write] {out_path}")


if __name__ == "__main__":
    main()
