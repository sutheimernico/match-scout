"""D7: the pre-match vs. closing gap computation, pinned on a hand-checkable fixture."""

from __future__ import annotations

import pandas as pd
import pytest

from matchscout.evaluation.odds_gap import findings, gap_report, price_gaps


def _rows(match_id, book, closing, prices, market="1x2"):
    return [
        {
            "match_id": match_id,
            "market": market,
            "selection": sel,
            "book": book,
            "odds": price,
            "is_closing": closing,
        }
        for sel, price in prices.items()
    ]


def _odds():
    fair = {"H": 2.0, "D": 4.0, "A": 4.0}  # no vig: de-vig is the identity (0.5 / 0.25 / 0.25)
    moved = {"H": 1.6, "D": 16 / 3, "A": 16 / 3}  # vig-free too: H drifts in to 0.625 (+12.5 pp)
    rows = (
        _rows("m1", "B365", False, fair)
        + _rows("m1", "B365", True, moved)
        + _rows("m1", "PS", True, fair)  # the sharp close agrees with the taken price
        + _rows("m2", "B365", False, fair)
        + _rows("m2", "B365", True, fair)  # never moved
        + _rows("m2", "Avg", True, {"H": 2.0, "D": 4.0})  # incomplete book: skipped, not guessed
    )
    return pd.DataFrame(rows)


def test_gaps_are_de_vigged_probability_differences_per_reference_book():
    gaps = price_gaps(_odds(), {"m1": "E0", "m2": "E0"})
    b365 = gaps[(gaps["reference"] == "B365") & (gaps["match_id"] == "m1")].set_index("selection")
    assert b365.loc["H", "gap"] == pytest.approx(0.125)
    assert b365.loc["D", "gap"] == pytest.approx(-0.0625)
    assert set(gaps[gaps["reference"] == "PS"]["gap"]) == {0.0}
    assert gaps[gaps["reference"] == "Avg"].empty


def test_the_report_labels_a_segment_that_never_moves_as_weak():
    gaps = price_gaps(_odds(), {"m1": "E0", "m2": "E0"})
    report = {r["reference"]: r for r in gap_report(gaps, ["market", "reference"])}
    assert report["B365"]["n"] == 6
    assert report["B365"]["share_moved_1pp"] == pytest.approx(0.5)
    assert report["PS"]["clv_signal"] == "weak"
    assert report["PS"]["median_abs_pp"] == 0.0
    assert "WEAK" in findings([report["PS"]])[0]
