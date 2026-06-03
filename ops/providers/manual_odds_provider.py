#!/usr/bin/env python3
"""
P10.1 manual_odds_provider — manual_stub provider.

No API key needed. Does NOT fabricate odds.
For each (match, market) outputs a row with odds=null,
status=missing_market_coverage, confidence=0.0.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

# Market rules template — always present even for missing coverage
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
        "handicap_line_note": "Asian handicap; push → void/refund",
    },
    "total_goals": {
        "push_possible": True,
        "void_conditions": ["match_cancelled", "match_postponed_indefinitely"],
        "selections": ["over", "under"],
        "line_note": "including extra time? Usually no — 90min only. Confirm per competition.",
    },
    "btts": {
        "push_possible": False,
        "void_conditions": ["match_cancelled", "match_postponed_indefinitely"],
        "selections": ["yes", "no"],
    },
    "double_chance": {
        "push_possible": False,
        "void_conditions": ["match_cancelled", "match_postponed_indefinitely"],
        "selections": ["home_draw", "home_away", "draw_away"],
    },
}


class ManualOddsProvider:
    """
    manual_stub provider for P10.1.

    - Never generates fake odds.
    - Outputs one row per (match, market) with odds=null.
    - Status is always 'missing_market_coverage'.
    - confidence=0.0, source_url="".
    """
    name = "manual_stub"

    def fetch_odds(self, date: str, snapshot_label: str, matches: list, markets: list) -> list:
        """
        Returns a list of normalized odds rows.
        Each row has odds=null and status='missing_market_coverage'.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = []

        for m in matches:
            match_id = m.get("match_id", "unknown")
            home = m.get("home_team", "")
            away = m.get("away_team", "")

            for market in markets:
                # Generate a selection string for documentation purposes
                if market == "moneyline":
                    selections = ["home_win", "draw", "away_win"]
                elif market == "handicap":
                    selections = ["home_-0.5", "away_+0.5"]
                elif market == "total_goals":
                    selections = ["over_2.5", "under_2.5"]
                elif market == "btts":
                    selections = ["yes", "no"]
                elif market == "double_chance":
                    selections = ["home_draw", "home_away", "draw_away"]
                else:
                    selections = ["unknown"]

                for sel in selections:
                    snapshot_id = f"{match_id}_{snapshot_label}_{market}_{sel}_{self.name}"
                    rows.append({
                        "snapshot_id":              snapshot_id,
                        "match_id":                 match_id,
                        "market":                   market,
                        "selection":                sel,
                        "odds":                     None,
                        "bookmaker_or_provider":    "manual_stub",
                        "snapshot_label":           snapshot_label,
                        "fetched_at":               now,
                        "source_url":               "",
                        "confidence":               0.0,
                        "status":                   "missing_market_coverage",
                        "market_rules":             MARKET_RULES.get(market, {}),
                    })

        return rows
