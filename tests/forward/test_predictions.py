"""The prediction log: every forward forecast on record, first sighting wins, settled once."""

from __future__ import annotations

from matchscout.forward.predictions import (
    PREDICTED,
    SETTLED,
    current_predictions,
    load_prediction_events,
    record_predictions,
    settle_predictions,
)


def _row(mid="E0:2627:20261010:Arsenal:Chelsea", p_H=0.5, odds_H=2.0, ts="2026-10-08T06:47"):
    return {
        "match_id": mid,
        "p_H": p_H,
        "odds_H": odds_H,
        "timestamp_known": ts,
        "status": PREDICTED,
    }


def test_the_first_sighting_wins(tmp_path):
    path = tmp_path / "predictions.jsonl"
    assert len(record_predictions(path, [_row()])) == 1
    assert record_predictions(path, [_row(p_H=0.9, ts="2026-10-09T06:47")]) == []
    row = current_predictions(path).iloc[0]
    assert row["p_H"] == 0.5
    assert row["timestamp_known"] == "2026-10-08T06:47"


def test_an_unpriced_record_is_superseded_once_by_the_first_priced_one(tmp_path):
    path = tmp_path / "predictions.jsonl"
    record_predictions(path, [_row(odds_H=None, ts="2026-10-07T06:47")])
    assert record_predictions(path, [_row(odds_H=None, ts="2026-10-07T15:47")]) == []
    assert len(record_predictions(path, [_row(odds_H=2.1, ts="2026-10-08T06:47")])) == 1
    assert record_predictions(path, [_row(odds_H=2.4, ts="2026-10-08T15:47")]) == []
    assert current_predictions(path).iloc[0]["odds_H"] == 2.1
    assert len(load_prediction_events(path)) == 2  # the unpriced line stays on record


def test_a_prediction_settles_once_with_the_result(tmp_path):
    path = tmp_path / "predictions.jsonl"
    mid = "E0:2627:20261010:Arsenal:Chelsea"
    record_predictions(path, [_row(mid), _row("E0:2627:20261010:Leeds:Spurs")])

    written = settle_predictions(path, {mid: (1, 3)}, settled_at="2026-10-11T06:47")
    assert [w["match_id"] for w in written] == [mid]
    assert settle_predictions(path, {mid: (1, 3)}, settled_at="2026-10-12T06:47") == []

    rows = current_predictions(path).set_index("match_id")
    assert rows.loc[mid, "status"] == SETTLED
    assert rows.loc[mid, "result"] == "A"
    assert rows.loc[mid, "ft_away_goals"] == 3
    assert rows.loc["E0:2627:20261010:Leeds:Spurs", "status"] == PREDICTED
