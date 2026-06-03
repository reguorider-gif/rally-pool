"""
P10.0 Match provider abstract base class.
"""


class MatchProvider:
    """Unified interface for match data providers."""

    name = "base"

    def fetch_matches(self, date: str, days: int):
        """
        Fetch matches within the window [date, date+days].

        Returns:
            dict with keys: version, date, days, provider, fetched_at, source_policy, matches
            Each match is a dict with required fields:
                match_id, kickoff_at, home_team, away_team, competition, status,
                provider, source_url, fetched_at, confidence
        """
        raise NotImplementedError

    def fetch_results(self, date: str):
        """
        Fetch match results for date.

        Returns:
            dict with keys: version, date, provider, fetched_at, source_policy,
                           summary (total/finished/scheduled/missing_or_not_finished), results
            Each result is a dict with required fields:
                match_id, status, home_score, away_score, halftime_score,
                red_cards, injury_notes, provider, source_url, fetched_at,
                confidence, result_state
        """
        raise NotImplementedError
