"""
P10.1 OddsProvider abstract base class.
"""
from abc import ABC, abstractmethod


class OddsProvider(ABC):
    """
    Unified interface for odds data providers.

    Output must be a normalized list of odds rows.
    Do NOT pass third-party raw responses directly to the business JSON.
    """

    name = "base"

    @abstractmethod
    def fetch_odds(self, date: str, snapshot_label: str, matches: list, markets: list) -> list:
        """
        Fetch odds for all matches on `date`, for the given `markets`.

        Args:
            date:           "2026-06-03"
            snapshot_label:  "T-1h", "T-24h", etc.
            matches:         list of match dicts from matches/current.json
            markets:         list of market strings, e.g. ["moneyline", "handicap", "total_goals"]

        Returns:
            List of normalized odds row dicts. Each row must contain:
                snapshot_id, match_id, market, selection, odds,
                bookmaker_or_provider, snapshot_label, fetched_at,
                source_url, confidence, status, market_rules
        """
        raise NotImplementedError
