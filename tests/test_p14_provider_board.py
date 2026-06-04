import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.generate_eligible_board import build_eligible_board
from ops.validate_model_outputs import (
    normalize_receipt,
    parse_bet_receipt,
    run_validation,
    select_bet_receipt,
    validate_bet_ledger,
)


def test_parser_selects_bet_receipt_from_multiple_json_blocks():
    text = (
        '{"memory_update":{"note":"ignore me"}}\n'
        '{"model_account":"chatgpt","round_id":"run-6","bet_ledger":[{"board_id":"b","odds_row_id":"o"}]}'
    )
    selected = select_bet_receipt(parse_bet_receipt(text))
    assert selected["model_account"] == "chatgpt"
    assert selected["bet_ledger"][0]["odds_row_id"] == "o"


def test_fallback_match_becomes_analysis_only_not_accepted():
    matches = {
        "WARM-007": {
            "match_id": "WARM-007",
            "home_team": "France",
            "away_team": "Ivory Coast",
            "odds_home": 1.3,
        }
    }
    receipt = {
        "model_account": "chatgpt",
        "round_id": "run-6",
        "bet_ledger": [{
            "match": "France v Cote d'Ivoire",
            "market": "France win",
            "stake_gp": 100,
        }],
    }
    normalized = normalize_receipt(
        receipt,
        "chatgpt",
        "run-6",
        matches,
        {"odds": []},
        {"items": [], "summary": {"eligible_board_rows": 0}},
    )
    assert normalized["bet_ledger"] == []
    assert normalized["analysis_only_bets"][0]["valid_for_settlement"] is False
    assert normalized["analysis_only_bets"][0]["reason_code"] == "analysis_only_missing_provider_odds"


def test_accepted_bet_requires_odds_row_id():
    board = {
        "items": [{
            "board_id": "run-6:odds-1",
            "odds_row_id": "odds-1",
            "provider": "the_odds_api",
            "provider_snapshot_id": "snap",
            "match_id": "WC-A1",
            "market": "moneyline",
            "selection": "Mexico",
            "price": 1.36,
            "valid_for_settlement": True,
        }]
    }
    bet = {
        "board_id": "run-6:odds-1",
        "match_id": "WC-A1",
        "market": "moneyline",
        "selection": "Mexico",
        "stake": 100,
        "odds": 1.36,
    }
    errors = validate_bet_ledger(
        bet,
        {"WC-A1": {"match_id": "WC-A1"}},
        {"odds": [{"match_id": "WC-A1", "market": "moneyline", "selection": "Mexico", "odds": 1.36, "status": "ok"}]},
        board,
    )
    assert "odds_row_id_mismatch" in errors


def test_eligible_board_generation_has_provider_rows():
    board = build_eligible_board("run-6", "2026-06-03", "T-1h", "the_odds_api")
    assert board["summary"]["eligible_board_rows"] > 0
    row = board["items"][0]
    for key in [
        "board_id",
        "provider",
        "provider_snapshot_id",
        "odds_row_id",
        "match_id",
        "home_team",
        "away_team",
        "commence_time",
        "market",
        "selection",
        "price",
        "last_update",
        "valid_for_settlement",
    ]:
        assert key in row
    assert row["provider"] == "the_odds_api"
    assert row["valid_for_settlement"] is True


def test_settlement_readiness_blocks_fallback_only_run6():
    br, _, _ = run_validation("run-6", "2026-06-03", "T-1h", dry_run=True)
    readiness = br["settlement_readiness"]
    assert readiness["eligible_board_rows"] > 0
    assert readiness["provider_covered_accepted_bets"] == 0
    assert readiness["valid_for_settlement"] is False
    assert "no_provider_covered_accepted_bets" in readiness["blockers"]


def test_active_pool_has_twelve_seats_only():
    accounts = json.loads((ROOT / "data/pool/model_accounts/current.json").read_text(encoding="utf-8"))
    active = [m for m in accounts["models"] if m.get("status") == "active"]
    assert len(active) == 12
    names = {m["model_account"] for m in active}
    assert "claude" not in names
    assert "zhipu" not in names


def _run_all():
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"{len(tests)} P14 tests passed")


if __name__ == "__main__":
    _run_all()
