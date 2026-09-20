"""The ledger must be append-only, idempotent and impossible to double-settle."""

from __future__ import annotations

import json

from matchscout.forward.ledger import (
    PENDING,
    SETTLED,
    append_snapshot,
    bet_id,
    current_bets,
    load_events,
    load_snapshots,
    place_bets,
    settle_bets,
)


def _bet(match_id="E0:2627:20260920:Arsenal:Chelsea", market="1x2", selection="H", **over):
    row = {
        "bet_id": bet_id(match_id, market, selection),
        "match_id": match_id,
        "competition": "E0",
        "date": "2026-09-20",
        "market": market,
        "selection": selection,
        "book": "B365",
        "odds_taken": 2.1,
        "p_model": 0.55,
        "edge": 0.155,
        "stake": 10.0,
        "timestamp_known": "2026-09-19T08:00:00+00:00",
        "status": PENDING,
        "run_id": "2026-09-19",
        "trial_id": "abc123",
    }
    return {**row, **over}


def test_bet_id_is_fixture_market_selection():
    assert bet_id("m1", "1x2", "H") == "m1|1x2|H"
    assert bet_id("m1", "1x2", "H") != bet_id("m1", "1x2", "A")


def test_placing_the_same_bet_twice_is_a_no_op(tmp_path):
    path = tmp_path / "bets.jsonl"
    assert len(place_bets(path, [_bet()])) == 1
    assert place_bets(path, [_bet()]) == []
    assert len(load_events(path)) == 1


def test_duplicates_inside_one_call_are_collapsed(tmp_path):
    path = tmp_path / "bets.jsonl"
    assert len(place_bets(path, [_bet(), _bet()])) == 1


def test_placed_bets_round_trip_with_the_full_column_set(tmp_path):
    path = tmp_path / "bets.jsonl"
    place_bets(path, [_bet()])
    bets = current_bets(path)
    assert len(bets) == 1
    row = bets.iloc[0]
    assert row["status"] == PENDING
    assert row["odds_taken"] == 2.1
    assert row["won"] is None  # settlement fields exist but are empty until it settles


def test_settlement_appends_rather_than_rewrites(tmp_path):
    path = tmp_path / "bets.jsonl"
    placed = place_bets(path, [_bet()])
    settle_bets(
        path,
        [{"bet_id": placed[0]["bet_id"], "status": SETTLED, "won": True, "pnl": 11.0}],
    )
    events = load_events(path)
    assert len(events) == 2  # the original placement is still on the record
    assert events[0]["status"] == PENDING
    assert events[1]["status"] == SETTLED
    assert events[1]["odds_taken"] == 2.1  # settlement inherits the placement fields

    state = current_bets(path)
    assert len(state) == 1
    assert state.iloc[0]["status"] == SETTLED
    assert state.iloc[0]["pnl"] == 11.0


def test_a_settled_bet_cannot_settle_again(tmp_path):
    path = tmp_path / "bets.jsonl"
    placed = place_bets(path, [_bet()])
    settlement = {"bet_id": placed[0]["bet_id"], "status": SETTLED, "won": True, "pnl": 11.0}
    settle_bets(path, [settlement])
    assert settle_bets(path, [{**settlement, "pnl": 999.0}]) == []
    assert len(load_events(path)) == 2


def test_settling_an_unknown_bet_is_ignored(tmp_path):
    path = tmp_path / "bets.jsonl"
    assert settle_bets(path, [{"bet_id": "nope", "status": SETTLED}]) == []
    assert load_events(path) == []


def test_replacing_a_placed_bet_never_loses_the_original_price(tmp_path):
    path = tmp_path / "bets.jsonl"
    place_bets(path, [_bet(odds_taken=2.1)])
    place_bets(path, [_bet(odds_taken=3.5)])  # a better price later is NOT a new bet
    assert current_bets(path).iloc[0]["odds_taken"] == 2.1


def test_current_bets_on_an_empty_ledger_has_the_schema(tmp_path):
    bets = current_bets(tmp_path / "missing.jsonl")
    assert bets.empty
    assert "bet_id" in bets.columns and "clv" in bets.columns


def test_snapshots_append_in_order(tmp_path):
    path = tmp_path / "snap.jsonl"
    append_snapshot(path, {"run_id": "2026-09-19", "bankroll": 1000.0})
    append_snapshot(path, {"run_id": "2026-09-20", "bankroll": 1010.0})
    snaps = load_snapshots(path)
    assert [s["run_id"] for s in snaps] == ["2026-09-19", "2026-09-20"]
    assert json.loads(path.read_text().splitlines()[1])["bankroll"] == 1010.0
