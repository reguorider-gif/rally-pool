#!/usr/bin/env python3
"""
P10.1 the_odds_api_provider — The Odds API integration.

- API key is read ONLY from environment variable THE_ODDS_API_KEY.
- No key → returns provider_unavailable, writes data gap, does NOT crash.
- Never prints or writes the API key to logs or JSON.
- Raw responses may be saved to data/pool/odds_snapshots/raw/ for debugging,
  but the raw file must NOT contain the API key.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "data" / "pool" / "odds_snapshots" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Market mapping: system market → The Odds API market key
MARKET_MAP = {
    "moneyline":    "h2h",
    "handicap":     "spreads",
    "total_goals":  "totals",
    "btts":         None,   # not directly supported → manual_review
    "double_chance": None,   # not directly supported → manual_review
}

MARKET_RULES = {
    "moneyline": {
        "push_possible": False,
        "void_conditions": ["match_cancelled", "match_postponed_indefinitely"],
        "selections": ["home", "draw", "away"],
    },
    "handicap": {
        "push_possible": True,
        "void_conditions": ["match_cancelled", "match_postponed_indefinitely"],
        "selections": ["home_handicap", "away_handicap"],
        "note": "Asian handicap; push → void/refund",
    },
    "total_goals": {
        "push_possible": True,
        "void_conditions": ["match_cancelled", "match_postponed_indefinitely"],
        "selections": ["over", "under"],
        "note": "90 min only unless specified",
    },
}


class TheOddsApiProvider:
    """
    The Odds API provider.

    - Requires THE_ODDS_API_KEY env var.
    - If key is missing, fetch_odds() returns an empty list
      and sets a provider_unavailable flag in the snapshot.
    - Saves raw responses to raw/ for debugging (key redacted).
    """
    name = "the_odds_api"

    def __init__(self):
        self.api_key = os.environ.get("THE_ODDS_API_KEY", "")
        self.base_url = "https://api.the-odds-api.com/v4"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _redact_key(self, text: str) -> str:
        """Remove API key from text for safe logging."""
        if self.api_key:
            text = text.replace(self.api_key, "***REDACTED***")
        return text

    def _save_raw(self, date: str, snapshot_label: str, data: list):
        """Save raw API response (key redacted) for debugging."""
        raw_path = RAW_DIR / f"{date}_{snapshot_label}_{self.name}.json"
        safe_data = json.loads(self._redact_key(json.dumps(data)))
        raw_path.write_text(
            json.dumps({"note": "API key redacted", "data": safe_data}, indent=2),
            encoding="utf-8"
        )

    def _fetch_sport_odds(self, sport_key: str, market_key: str) -> list:
        """
        Fetch odds from The Odds API for a given sport and market.
        Returns raw API response list.
        """
        import urllib.request
        import urllib.error

        if not self.is_available():
            return []

        url = (
            f"{self.base_url}/sports/{sport_key}/odds"
            f"?apiKey={self.api_key}"
            f"&markets={market_key}"
            f"&oddsFormat=decimal"
        )

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data if isinstance(data, list) else []
        except Exception as e:
            print(f"  [the_odds_api] fetch error for {sport_key}/{market_key}: {e}")
            return []

    def fetch_odds(self, date: str, snapshot_label: str, matches: list, markets: list) -> list:
        """
        Fetch odds from The Odds API.

        Returns normalized odds rows.
        If provider is unavailable (no API key), returns empty list
        and the caller should write a provider_unavailable gap.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if not self.is_available():
            print("  [the_odds_api] WARNING: THE_ODDS_API_KEY not set — provider unavailable")
            return []  # caller writes provider_unavailable gap

        rows = []
        sport_key = "soccer_fifa_wc"  # FIFA World Cup 2026

        for market in markets:
            api_market = MARKET_MAP.get(market)
            if api_market is None:
                # Market not supported → write manual_review row
                for m in matches:
                    snapshot_id = f"{m.get('match_id')}_{snapshot_label}_{market}_manual_review_{self.name}"
                    rows.append({
                        "snapshot_id":            snapshot_id,
                        "match_id":               m.get("match_id"),
                        "market":                 market,
                        "selection":              "manual_review",
                        "odds":                   None,
                        "bookmaker_or_provider":  self.name,
                        "snapshot_label":         snapshot_label,
                        "fetched_at":             now,
                        "source_url":             f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
                        "confidence":             0.0,
                        "status":                 "market_not_supported",
                        "market_rules":           MARKET_RULES.get(market, {}),
                    })
                continue

            raw_data = self._fetch_sport_odds(sport_key, api_market)
            self._save_raw(date, snapshot_label, raw_data)

            # Match third-party games to internal match_id by team name + kickoff
            for game in raw_data:
                away_team = game.get("away_team", "")
                home_team = game.get("home_team", "")
                # Best-effort match by team name (partial match)
                matched_match_id = None
                for m in matches:
                    if (m.get("home_team", "") in home_team or home_team in m.get("home_team", "")) and \
                       (m.get("away_team", "") in away_team or away_team in m.get("away_team", "")):
                        matched_match_id = m.get("match_id")
                        break

                if not matched_match_id:
                    # Write match_mapping_failed row
                    snapshot_id = f"unmapped_{snapshot_label}_{market}_{self.name}"
                    rows.append({
                        "snapshot_id":            snapshot_id,
                        "match_id":               None,
                        "market":                 market,
                        "selection":              "match_mapping_failed",
                        "odds":                   None,
                        "bookmaker_or_provider":  self.name,
                        "snapshot_label":         snapshot_label,
                        "fetched_at":             now,
                        "source_url":             game.get("link", ""),
                        "confidence":             0.0,
                        "status":                 "match_mapping_failed",
                        "market_rules":           MARKET_RULES.get(market, {}),
                    })
                    continue

                # Parse bookmaker odds from the response
                for bookmaker in game.get("bookmakers", []):
                    bm_name = bookmaker.get("title", "unknown")
                    for outcome in bookmaker.get("markets", [{}])[0].get("outcomes", []):
                        selection = outcome.get("name", "unknown")
                        price = outcome.get("price")
                        if price is not None and price > 0:
                            rows.append({
                                "snapshot_id":            f"{matched_match_id}_{snapshot_label}_{market}_{selection}_{bm_name}_{self.name}",
                                "match_id":               matched_match_id,
                                "market":                 market,
                                "selection":              selection,
                                "odds":                   round(float(price), 3),
                                "bookmaker_or_provider":  bm_name,
                                "snapshot_label":         snapshot_label,
                                "fetched_at":             now,
                                "source_url":             game.get("link", ""),
                                "confidence":             0.9,
                                "status":                 "ok",
                                "market_rules":           MARKET_RULES.get(market, {}),
                            })

            # Rate-limit: be nice to the API
            time.sleep(0.2)

        return rows
