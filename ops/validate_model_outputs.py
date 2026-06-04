#!/usr/bin/env python3
from __future__ import annotations
"""
P10.2 validate_model_outputs — validate model outputs, match against odds snapshots,
and generate bet receipts (accepted / manual_review / rejected).

Usage:
  python3 ops/validate_model_outputs.py --round run-5 --date 2026-06-03 --snapshot-label T-1h --dry-run
  python3 ops/validate_model_outputs.py --round run-5 --date 2026-06-03 --snapshot-label T-1h
  python3 ops/validate_model_outputs.py --round run-5 --date 2026-06-03 --snapshot-label T-1h --verbose
"""

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "pool"
sys.path.insert(0, str(BASE_DIR))

VALID_MARKETS = {"moneyline", "handicap", "total_goals", "btts", "double_chance"}

TEAM_ALIASES = {
    "cote d ivoire": "ivory coast",
    "cote divoire": "ivory coast",
    "côte d ivoire": "ivory coast",
    "united states": "usa",
    "u s a": "usa",
    "republic of ireland": "ireland",
}


# ── helpers ──────────────────────────────────────────────────────────────────
def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"  [error] file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_json_from_text(text: str) -> list:
    """Try to extract JSON objects from raw text using balanced brace matching."""
    results = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start : i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        results.append(obj)
                except (json.JSONDecodeError, ValueError):
                    pass
                start = -1
    return results


def parse_bet_receipt(text: str) -> list:
    """Extract bet receipt JSON objects from raw_text."""
    if not text or not isinstance(text, str):
        return []
    return extract_json_from_text(text)


def _norm(value: str) -> str:
    """Normalize loose model/team text for matching."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for alias, canonical in TEAM_ALIASES.items():
        text = text.replace(alias, canonical)
    return text


def _receipt_score(obj: dict) -> int:
    """Prefer the JSON block that looks like a betting receipt, not memory_update."""
    if not isinstance(obj, dict):
        return -1
    score = 0
    if isinstance(obj.get("bet_ledger"), list):
        score += 100 + len(obj.get("bet_ledger", []))
    if isinstance(obj.get("bets"), list):
        score += 80 + len(obj.get("bets", []))
    if "loan_decision" in obj or "investment_loan" in obj:
        score += 10
    if "memory_update" in obj:
        score -= 50
    return score


def select_bet_receipt(candidates: list) -> dict | None:
    """Select the best structured betting object from parsed JSON candidates."""
    ranked = [c for c in candidates if isinstance(c, dict)]
    if not ranked:
        return None
    best = max(ranked, key=_receipt_score)
    return best if _receipt_score(best) > 0 else None


def _match_from_label(label: str, matches_map: dict) -> dict | None:
    text = _norm(label)
    if not text:
        return None
    for match in matches_map.values():
        home = _norm(match.get("home_team", ""))
        away = _norm(match.get("away_team", ""))
        if home and away and home in text and away in text:
            return match
    return None


def _selection_from_market_text(market_text: str, match: dict) -> str:
    text = _norm(market_text)
    home = _norm(match.get("home_team", ""))
    away = _norm(match.get("away_team", ""))
    if "draw" in text and "draw no bet" not in text and "dnb" not in text:
        return "Draw"
    if home and home in text:
        return match.get("home_team", "")
    if away and away in text:
        return match.get("away_team", "")
    return ""


def _market_from_text(market_text: str) -> str:
    text = _norm(market_text)
    if "win" in text or "draw no bet" in text or "dnb" in text:
        return "moneyline"
    if "under" in text or "over" in text or "小" in market_text or "大" in market_text:
        return "total_goals"
    if "both teams" in text or "btts" in text:
        return "btts"
    if "double chance" in text:
        return "double_chance"
    if "handicap" in text or re.search(r"(^|\s)[+-]\d", market_text):
        return "handicap"
    return "moneyline"


def _fallback_moneyline_odds(match: dict, selection: str) -> float | None:
    sel = _norm(selection)
    if sel == _norm(match.get("home_team", "")):
        return match.get("odds_home")
    if sel == "draw":
        return match.get("odds_draw")
    if sel == _norm(match.get("away_team", "")):
        return match.get("odds_away")
    return None


def _normalize_bet(raw_bet: dict, matches_map: dict, odds_snapshot: dict) -> tuple:
    """Normalize common web-model bet JSON into the internal bet_ledger shape."""
    if not isinstance(raw_bet, dict):
        return None, "bet_not_object"

    match_id = raw_bet.get("match_id")
    match = matches_map.get(match_id) if match_id else None
    if match is None:
        match = _match_from_label(str(raw_bet.get("match") or raw_bet.get("fixture") or ""), matches_map)
        match_id = match.get("match_id") if match else None
    if match is None or not match_id:
        return None, "match_not_mapped"

    raw_market = str(raw_bet.get("market") or raw_bet.get("selection") or "")
    market = raw_bet.get("market_type") or raw_bet.get("market_key") or raw_bet.get("market")
    if market not in VALID_MARKETS:
        market = _market_from_text(raw_market)

    selection = raw_bet.get("selection")
    if not selection or not isinstance(selection, str):
        selection = _selection_from_market_text(raw_market, match)
    if not selection:
        return None, "selection_not_mapped"

    stake = raw_bet.get("stake")
    if stake is None:
        stake = raw_bet.get("stake_gp")
    if not isinstance(stake, (int, float)) or stake <= 0:
        return None, "stake_not_mapped"

    odds_val = raw_bet.get("odds")
    odds_source = raw_bet.get("odds_source") or ""
    provider_row = find_odds_match(odds_snapshot, match_id, market, selection)
    if provider_row:
        odds_val = provider_row.get("odds")
        odds_source = "the_odds_api"
    elif not isinstance(odds_val, (int, float)) or odds_val <= 1:
        fallback = _fallback_moneyline_odds(match, selection) if market == "moneyline" else None
        if isinstance(fallback, (int, float)) and fallback > 1:
            odds_val = fallback
            odds_source = "matches_current_fallback"
        else:
            return None, "odds_not_mapped"

    normalized = {
        "bet_id": raw_bet.get("bet_id") or f"{match_id}-{market}-{selection}",
        "match_id": match_id,
        "market": market,
        "selection": selection,
        "stake": stake,
        "odds": odds_val,
        "confidence": raw_bet.get("confidence"),
        "odds_source": odds_source or "model_supplied",
        "source_basis": raw_bet.get("source_basis", []),
        "cancel_conditions": raw_bet.get("cancel_conditions", []),
        "raw_market": raw_bet.get("market"),
    }
    return normalized, ""


def normalize_receipt(receipt: dict, model_account: str, round_id: str,
                      matches_map: dict, odds_snapshot: dict) -> dict:
    """Bridge model-facing receipt variants into the validator schema."""
    normalized = dict(receipt)
    raw_bets = receipt.get("bet_ledger")
    if not isinstance(raw_bets, list):
        raw_bets = receipt.get("bets")

    skipped = []
    bet_ledger = []
    if isinstance(raw_bets, list):
        for raw_bet in raw_bets:
            bet, reason = _normalize_bet(raw_bet, matches_map, odds_snapshot)
            if bet:
                bet_ledger.append(bet)
            else:
                skipped.append({"reason": reason, "bet": raw_bet})
        normalized["bet_ledger"] = bet_ledger
        normalized["non_executable_bets"] = skipped

    if "loan_decision" not in normalized:
        amount = normalized.get("investment_loan", normalized.get("loan_amount", 0))
        if not isinstance(amount, (int, float)):
            amount = 0
        normalized["loan_decision"] = {
            "type": "investment_loan" if amount else "none",
            "amount": amount,
        }

    normalized["round_id"] = normalized.get("round_id") or normalized.get("run_id") or round_id
    normalized["model_account"] = normalized.get("model_account") or normalized.get("seat_id") or model_account
    if normalized["model_account"] == "grok":
        normalized["model_account"] = "xai"
    return normalized


def is_eligible_model(run: dict) -> bool:
    """Check if model is eligible for consensus — both conditions must be true."""
    status = run.get("status", "")
    eligible = run.get("eligible_for_consensus", False)
    return status == "valid_receipt" and eligible is True


def load_odds_snapshot(date: str, snapshot_label: str) -> dict:
    """Load odds snapshot, return empty dict on failure."""
    provider_specific = DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}_the_odds_api.json"
    if provider_specific.exists():
        data = load_json(provider_specific)
        summary = data.get("summary") or data.get("data", {}).get("summary") or {}
        if summary.get("valid_odds_rows", 0) > 0 or data.get("odds"):
            return data
    p = DATA_DIR / "odds_snapshots" / f"{date}_{snapshot_label}.json"
    if p.exists():
        return load_json(p)
    return {"odds": [], "summary": {}}


def find_odds_match(odds_snapshot: dict, match_id: str, market: str,
                    selection: str) -> dict | None:
    """Find a valid odds row matching match_id + market + selection."""
    for row in odds_snapshot.get("odds", []):
        if row.get("match_id") != match_id:
            continue
        if row.get("market") != market:
            continue
        # best-effort selection matching
        if row.get("selection", "").strip().lower() != selection.strip().lower():
            continue
        odds_val = row.get("odds")
        status = row.get("status", "")
        # Must have valid odds
        if odds_val is not None and isinstance(odds_val, (int, float)) and odds_val > 1:
            if status not in ("missing_market_coverage", "provider_unavailable",
                              "match_mapping_failed", "manual_review"):
                return row
    return None


def validate_bet_ledger(bet: dict, matches_map: dict, odds_snapshot: dict,
                        verbose: bool = False) -> list:
    """Validate a single bet ledger entry. Returns list of error reason_codes (empty = valid)."""
    errors = []

    # match_id check
    mid = bet.get("match_id")
    if not mid or mid not in matches_map:
        errors.append("invalid_match_id")

    # market check
    market = bet.get("market", "")
    if market not in VALID_MARKETS:
        if market == "manual_review":
            pass  # allowed
        else:
            errors.append("unsupported_market")

    # selection check
    selection = bet.get("selection")
    if not selection or not isinstance(selection, str) or not selection.strip():
        errors.append("missing_required_field")  # no selection

    # stake check
    stake = bet.get("stake")
    if not isinstance(stake, (int, float)) or stake <= 0:
        errors.append("invalid_stake")

    # odds check
    odds_val = bet.get("odds")
    if not isinstance(odds_val, (int, float)) or odds_val <= 1:
        errors.append("invalid_odds")

    # confidence check
    conf = bet.get("confidence")
    if conf is not None:
        if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
            errors.append("invalid_confidence")

    # odds snapshot matching (only if bet passed field checks)
    if not errors and mid and market and selection:
        if bet.get("odds_source") == "matches_current_fallback":
            return errors
        match = find_odds_match(odds_snapshot, mid, market, selection)
        if match is None:
            # Check if market coverage even exists for this match+market
            has_coverage = False
            for row in odds_snapshot.get("odds", []):
                if row.get("match_id") == mid and row.get("market") == market:
                    has_coverage = True
                    break
            if has_coverage:
                errors.append("odds_selection_not_matched")
            else:
                errors.append("odds_snapshot_no_valid_market_coverage")

    return errors


# ── main pipeline ────────────────────────────────────────────────────────────
def run_validation(round_id: str, date: str, snapshot_label: str,
                   dry_run: bool = False, verbose: bool = False,
                   allow_manual_review: bool = True):
    """Main validation pipeline."""

    print("validate_model_outputs")
    print(f"  round_id:       {round_id}")
    print(f"  date:           {date}")
    print(f"  snapshot_label: {snapshot_label}")
    print(f"  dry_run:        {dry_run}")
    print(f"  verbose:        {verbose}")

    # ── Load inputs ──
    runs_data = load_json(DATA_DIR / "model_runs" / f"{round_id}.json")
    outputs_data = load_json(DATA_DIR / "model_outputs" / f"{round_id}.json")
    rerun_data = load_json(DATA_DIR / "rerun_queue" / f"{round_id}.json")
    matches_data = load_json(DATA_DIR / "matches" / "current.json")
    odds_snapshot = load_odds_snapshot(date, snapshot_label)
    leaderboard_data = load_json(DATA_DIR / "leaderboard" / "current.json")

    # Build maps
    runs_map = {r["model_account"]: r for r in runs_data.get("runs", [])}
    matches_map = {m["match_id"]: m for m in matches_data.get("matches", [])}
    lb_map = {e.get("model_account", ""): e for e in leaderboard_data.get("leaderboard", [])}

    models_total = runs_data.get("summary", {}).get("total", len(runs_map))

    print(f"  models_total:   {models_total}")

    # ── Per-model processing ──
    accepted_receipts = []
    manual_review_receipts = []
    rejections = []

    eligible_count = 0
    structured_count = 0
    candidate_bets = 0

    for output_entry in outputs_data.get("outputs", []):
        ma = output_entry.get("model_account", "unknown")
        run_entry = runs_map.get(ma, {})
        is_eligible = is_eligible_model(run_entry)

        if is_eligible:
            eligible_count += 1

        # ── Try to extract bet receipt ──
        raw = output_entry.get("raw_text", "")
        candidates = []
        parsed_json = output_entry.get("parsed_json")
        if isinstance(parsed_json, dict):
            candidates.append(parsed_json)
        candidates.extend(parse_bet_receipt(raw))
        receipt = select_bet_receipt(candidates)
        if receipt is not None:
            receipt = normalize_receipt(receipt, ma, round_id, matches_map, odds_snapshot)
            if verbose:
                print(f"  {ma}: selected betting receipt from {len(candidates)} JSON block(s)")

        if receipt is None or not isinstance(receipt, dict):
            # No structured receipt
            if not is_eligible:
                rejections.append({
                    "model_account": ma,
                    "stage": "model_eligibility",
                    "reason_code": "model_not_eligible_for_consensus",
                    "reason": f"Model status is '{run_entry.get('status')}', eligible_for_consensus={run_entry.get('eligible_for_consensus')}",
                    "source_path": str(DATA_DIR / "model_outputs" / f"{round_id}.json"),
                })
            else:
                rejections.append({
                    "model_account": ma,
                    "stage": "receipt_extraction",
                    "reason_code": "no_structured_bet_receipt",
                    "reason": "No structured bet receipt JSON found in model output (parsed_json empty, raw_text contains no valid JSON receipt).",
                    "source_path": str(DATA_DIR / "model_outputs" / f"{round_id}.json"),
                })
            continue

        # ── Has structured receipt ──
        structured_count += 1

        if not is_eligible:
            rejections.append({
                "model_account": ma,
                "stage": "model_eligibility",
                "reason_code": "model_not_eligible_for_consensus",
                "reason": f"Model status is '{run_entry.get('status')}', eligible_for_consensus={run_entry.get('eligible_for_consensus')}",
                "source_path": str(DATA_DIR / "model_outputs" / f"{round_id}.json"),
            })
            continue

        # ── Field-level validation ──
        bet_ledger = receipt.get("bet_ledger", receipt.get("bet ledger", []))
        if not isinstance(bet_ledger, list):
            rejections.append({
                "model_account": ma,
                "stage": "field_validation",
                "reason_code": "missing_required_field",
                "reason": "bet_ledger is not a list.",
                "source_path": str(DATA_DIR / "model_outputs" / f"{round_id}.json"),
            })
            continue

        all_errors = []
        bet_errors = []
        for bet in bet_ledger:
            candidate_bets += 1
            errs = validate_bet_ledger(bet, matches_map, odds_snapshot, verbose)
            bet_errors.append({"bet": bet, "errors": errs})
            all_errors.extend(errs)

        # ── Risk / fund checks ──
        total_stake = sum(bet.get("stake", 0) for bet in bet_ledger
                          if isinstance(bet.get("stake"), (int, float)))
        risk_rules = receipt.get("risk_rules", receipt.get("risk rules", {}))
        max_loss = risk_rules.get("max_loss")
        if isinstance(max_loss, (int, float)) and total_stake > max_loss:
            all_errors.append("stake_exceeds_max_loss")

        loan_decision = receipt.get("loan_decision", receipt.get("loan decision", {}))
        loan_amount = loan_decision.get("amount")
        if not isinstance(loan_amount, (int, float)) or loan_amount < 0:
            all_errors.append("loan_amount_invalid")

        # Balance check (optional — don't hard reject)
        lb_entry = lb_map.get(ma, {})
        balance = lb_entry.get("balance_gp")
        if balance is not None and isinstance(balance, (int, float)):
            approved_loan = loan_amount if isinstance(loan_amount, (int, float)) else 0
            available = balance + approved_loan
            if total_stake > available:
                all_errors.append("stake_exceeds_available_balance")
        else:
            if verbose:
                print(f"  {ma}: balance_unknown (no leaderboard entry)")

        # ── Round_id / model_account checks ──
        receipt_round = receipt.get("round_id")
        if receipt_round and receipt_round != round_id:
            all_errors.append("round_id_mismatch")
        receipt_ma = receipt.get("model_account")
        if receipt_ma and receipt_ma != ma:
            all_errors.append("model_account_mismatch")

        # ── Decide outcome ──
        if all_errors:
            # Check if any errors warrant manual_review
            review_only = all(e in ("balance_unknown_manual_review",)
                              for e in all_errors)
            if review_only and allow_manual_review:
                manual_review_receipts.append({
                    "model_account": ma,
                    "round_id": round_id,
                    "receipt": receipt,
                    "bet_errors": bet_errors,
                    "issues": all_errors,
                })
            else:
                rejections.append({
                    "model_account": ma,
                    "stage": "validation",
                    "reason_code": ",".join(sorted(set(all_errors))),
                    "reason": f"Bet receipt validation failed: {', '.join(sorted(set(all_errors)))}",
                    "bet_errors": bet_errors,
                    "source_path": str(DATA_DIR / "model_outputs" / f"{round_id}.json"),
                })
        else:
            # All checks passed
            accepted_receipts.append({
                "model_account": ma,
                "round_id": round_id,
                "receipt": receipt,
                "total_stake": total_stake,
                "bet_count": len(bet_ledger),
                "loan_amount": loan_amount,
            })

    # ── Summary ──
    accepted_bets = sum(r.get("bet_count", 0) for r in accepted_receipts)
    manual_review_bets = len(manual_review_receipts)
    rejected_bets = len(rejections)
    provider_bets = sum(
        1
        for r in accepted_receipts
        for bet in r.get("receipt", {}).get("bet_ledger", [])
        if bet.get("odds_source") == "the_odds_api"
    )
    fallback_bets = sum(
        1
        for r in accepted_receipts
        for bet in r.get("receipt", {}).get("bet_ledger", [])
        if bet.get("odds_source") == "matches_current_fallback"
    )

    # Count rejection reasons
    reason_counts = {}
    for rj in rejections:
        rc = rj.get("reason_code", "unknown")
        reason_counts[rc] = reason_counts.get(rc, 0) + 1

    ineligible_count = models_total - eligible_count

    summary = {
        "models_total": models_total,
        "models_eligible": eligible_count,
        "models_ineligible": ineligible_count,
        "models_with_structured_receipts": structured_count,
        "candidate_bets": candidate_bets,
        "accepted_bets": accepted_bets,
        "provider_bets": provider_bets,
        "fallback_bets": fallback_bets,
        "manual_review_bets": manual_review_bets,
        "rejected_bets": rejected_bets,
        "valid_for_settlement": accepted_bets > 0,
    }

    print(f"  eligible:       {eligible_count}/{models_total}")
    print(f"  structured:     {structured_count}")
    print(f"  accepted_bets:  {accepted_bets}")
    print(f"  manual_review:  {manual_review_bets}")
    print(f"  rejected:       {rejected_bets}")

    # Build bet receipts output
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bet_receipt_file = {
        "version": "p10.2",
        "round_id": round_id,
        "date": date,
        "snapshot_label": snapshot_label,
        "generated_at": now,
        "summary": summary,
        "accepted_receipts": accepted_receipts,
        "manual_review_receipts": manual_review_receipts,
        "source_files": [
            f"data/pool/model_runs/{round_id}.json",
            f"data/pool/model_outputs/{round_id}.json",
            f"data/pool/odds_snapshots/{date}_{snapshot_label}.json",
            f"data/pool/matches/current.json",
            f"data/pool/leaderboard/current.json",
        ],
    }

    # Build rejections output
    rejections_file = {
        "version": "p10.2",
        "round_id": round_id,
        "date": date,
        "generated_at": now,
        "summary": {
            "rejected_models": len(set(rj["model_account"] for rj in rejections)),
            "rejected_bets": rejected_bets,
            "reason_counts": reason_counts,
        },
        "rejections": rejections,
    }

    # Build index
    idx_path = DATA_DIR / "bet_receipts" / "index.json"
    existing_rounds = []
    if idx_path.exists():
        try:
            existing = load_json(idx_path)
            existing_rounds = existing.get("rounds", [])
        except Exception:
            pass

    round_entry = {
        "round_id": round_id,
        "date": date,
        "path": f"data/pool/bet_receipts/{round_id}.json",
        "rejections_path": f"data/pool/bet_receipts/rejections/{round_id}.json",
        "accepted_bets": accepted_bets,
        "manual_review_bets": manual_review_bets,
        "rejected_bets": rejected_bets,
        "valid_for_settlement": accepted_bets > 0,
    }

    # Update or append round in index
    existing_by_round = {r["round_id"]: r for r in existing_rounds}
    existing_by_round[round_id] = round_entry
    updated_rounds = list(existing_by_round.values())

    index_file = {
        "version": "p10.2",
        "updated_at": now,
        "rounds": updated_rounds,
    }

    # ── Write outputs ──
    if dry_run:
        print("  [dry-run] no files written")
        return bet_receipt_file, rejections_file, index_file

    bet_dir = DATA_DIR / "bet_receipts"
    rej_dir = bet_dir / "rejections"
    bet_dir.mkdir(parents=True, exist_ok=True)
    rej_dir.mkdir(parents=True, exist_ok=True)

    out_br = bet_dir / f"{round_id}.json"
    out_rj = rej_dir / f"{round_id}.json"

    with open(out_br, "w", encoding="utf-8") as f:
        json.dump(bet_receipt_file, f, ensure_ascii=False, indent=2)
    print(f"  [write] {out_br}")

    with open(out_rj, "w", encoding="utf-8") as f:
        json.dump(rejections_file, f, ensure_ascii=False, indent=2)
    print(f"  [write] {out_rj}")

    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index_file, f, ensure_ascii=False, indent=2)
    print(f"  [write] {idx_path}")

    return bet_receipt_file, rejections_file, index_file


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="P10.2 validate model outputs")
    parser.add_argument("--round", required=True, help="Round ID (e.g. run-5)")
    parser.add_argument("--date", required=True, help="Date (e.g. 2026-06-03)")
    parser.add_argument("--snapshot-label", default="T-1h", help="Snapshot label")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--allow-manual-review", action="store_true", default=True,
                        help="Allow manual_review classification")
    args = parser.parse_args()

    run_validation(
        round_id=args.round,
        date=args.date,
        snapshot_label=args.snapshot_label,
        dry_run=args.dry_run,
        verbose=args.verbose,
        allow_manual_review=args.allow_manual_review,
    )


if __name__ == "__main__":
    main()
