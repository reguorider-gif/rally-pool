"""
P10.0 Legacy seed provider — reads from existing data/pool/matches/current.json.

No external network calls.
Confidence capped at 0.5 when source_url is empty.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from .match_provider_base import MatchProvider

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # pool-app/
DATA_DIR = BASE_DIR / "data" / "pool"


class LegacySeedProvider(MatchProvider):
    name = "legacy_seed"

    def __init__(self):
        self._matches_file = DATA_DIR / "matches" / "current.json"

    def _load_matches(self):
        """Load matches from current.json."""
        if not self._matches_file.exists():
            return []
        data = json.loads(self._matches_file.read_text(encoding="utf-8"))
        return data.get("matches", [])

    def _normalize_match(self, m, fetched_at):
        """Normalise a legacy match to P10.0 provider format."""
        # Use 'date' as kickoff_at if no kickoff_at field
        kickoff = m.get("kickoff_at") or (m.get("date", "") + "T00:00:00Z")
        return {
            "match_id":    m.get("match_id", ""),
            "kickoff_at":  kickoff,
            "home_team":   m.get("home_team", ""),
            "home_flag":   m.get("home_flag", ""),
            "away_team":   m.get("away_team", ""),
            "away_flag":   m.get("away_flag", ""),
            "competition": m.get("competition", ""),
            "status":      m.get("status", "scheduled"),
            "provider":    self.name,
            "source_url":  m.get("source_url", ""),
            "fetched_at":  fetched_at,
            "confidence":  min(m.get("confidence", 0.5), 0.5),
            # retain odds/prob for downstream use
            "odds_home":   m.get("odds_home"),
            "odds_draw":   m.get("odds_draw"),
            "odds_away":   m.get("odds_away"),
            "prob_home":   m.get("prob_home"),
            "prob_draw":   m.get("prob_draw"),
            "prob_away":   m.get("prob_away"),
        }

    def fetch_matches(self, date: str, days: int):
        """
        Read matches from current.json, filter by date window.

        Returns P10.0-compatible matches dict.
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        matches = self._load_matches()
        # Parse date range
        from datetime import datetime as dt
        try:
            start = dt.strptime(date, "%Y-%m-%d")
        except ValueError:
            start = dt.strptime("2026-06-03", "%Y-%m-%d")
        end = start.replace()  # simple copy; window filtering is approximate
        # In first version, return all matches regardless of window
        # (legacy seed has no real date filtering)
        normalized = [self._normalize_match(m, now_utc) for m in matches]

        return {
            "version":       "p10.0",
            "date":          date,
            "days":          days,
            "provider":      self.name,
            "fetched_at":    now_utc,
            "source_policy": "legacy_seed_no_external_fetch",
            "matches":       normalized,
        }

    def fetch_results(self, date: str):
        """
        Generate result records from existing matches.

        If no real results are available, ALL matches are marked as
        scheduled/unknown with null scores.
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        matches = self._load_matches()

        results = []
        finished_count = 0
        scheduled_count = 0
        missing_count = 0

        for m in matches:
            status = m.get("status", "scheduled")
            home_score = m.get("home_score")
            away_score = m.get("away_score")

            # Only trust scores if status is settled/finished and scores are numeric
            if status in ("settled", "finished") and isinstance(home_score, (int, float)) and isinstance(away_score, (int, float)):
                result_state = "finished"
                finished_count += 1
                # P10.0 rule: confidence capped at 0.5 when source_url is empty
                has_source = bool(m.get("source_url", "").strip())
                confidence = 0.9 if has_source else 0.5
            else:
                home_score = None
                away_score = None
                result_state = "missing_or_not_finished"
                missing_count += 1
                confidence = 0.5
                if status not in ("settled", "finished"):
                    scheduled_count += 1

            results.append({
                "match_id":       m.get("match_id", ""),
                "status":         status if status in ("scheduled", "finished", "live", "settled") else "scheduled",
                "home_score":     home_score,
                "away_score":     away_score,
                "halftime_score": None,
                "red_cards":      [],
                "injury_notes":   [],
                "provider":       self.name,
                "source_url":     m.get("source_url", ""),
                "fetched_at":     now_utc,
                "confidence":     confidence,
                "result_state":       result_state,
                "extra_time":         None,
                "penalties":          None,
            })

        return {
            "version":       "p10.0",
            "date":          date,
            "provider":      self.name,
            "fetched_at":    now_utc,
            "source_policy": "legacy_seed_no_external_fetch",
            "summary": {
                "total":                    len(results),
                "finished":                finished_count,
                "scheduled":               scheduled_count,
                "missing_or_not_finished": missing_count,
            },
            "results": results,
        }
