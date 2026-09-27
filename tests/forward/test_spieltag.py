"""The German Spieltag page renders every state from the logs alone and never hides the caveat."""

from __future__ import annotations

import pandas as pd

from matchscout.forward.ledger import BET_COLUMNS
from matchscout.forward.predictions import PREDICTION_COLUMNS
from matchscout.forward.report import forward_record
from matchscout.forward.spieltag import DISCLAIMER, backtest_line, render_spieltag

NOW = pd.Timestamp("2026-10-08T06:47:00Z")
MID = "D1:2627:20261010:Bayern Munich:Dortmund"


def _pred(**over):
    row = {
        "match_id": MID,
        "competition": "D1",
        "date": "2026-10-10",
        "kickoff": "2026-10-10 17:30:00",
        "p_H": 0.62, "p_D": 0.2, "p_A": 0.18, "p_over": 0.66, "p_under": 0.34,
        "odds_H": 1.5, "mkt_H": 0.64, "mkt_D": 0.2, "mkt_A": 0.16, "mkt_over": 0.7,
        "timestamp_known": "2026-10-08T06:47:00+00:00",
        "status": "predicted",
    }
    return {**row, **over}


def _page(bets, preds, backtest=None):
    bets = pd.DataFrame(bets, columns=BET_COLUMNS)
    preds = pd.DataFrame(preds, columns=PREDICTION_COLUMNS)
    return render_spieltag(
        bets, preds, forward_record(bets, preds), now=NOW, backtest=backtest
    )


def test_the_empty_page_says_why_it_is_empty_and_keeps_the_disclaimer():
    page = _page([], [])
    assert DISCLAIMER in page
    assert "keine Top-5-Spiele" in page
    assert "noch ohne Einträge" in page


def test_an_upcoming_fixture_shows_model_market_and_german_kickoff_time():
    bet = {
        "bet_id": f"{MID}|1x2|A", "match_id": MID, "competition": "D1", "date": "2026-10-10",
        "market": "1x2", "selection": "A", "odds_taken": 7.0, "edge": 0.26, "stake": 10.0,
        "timestamp_known": "2026-10-08T06:47:00+00:00", "status": "pending",
    }
    page = _page([bet], [_pred()])
    assert "Bundesliga" in page
    assert "Bayern Munich – Dortmund" in page
    assert "Sa 10.10. 18:30" in page  # UK 17:30 is German 18:30
    assert "62 % / 20 % / 18 %" in page
    assert "2 (Gast) @ 7,00" in page
    assert "keine Top-5-Spiele" not in page


def test_team_names_are_escaped():
    page = _page([], [_pred(match_id="D1:2627:20261010:<b>X</b>:Y")])
    assert "<b>X</b>" not in page
    assert "&lt;b&gt;X&lt;/b&gt;" in page


def test_a_settled_prediction_shows_the_score_and_whether_the_tip_hit():
    settled = _pred(status="settled", ft_home_goals=1, ft_away_goals=2, result="A")
    page = _page([], [settled])
    assert "1:2" in page
    assert "1 ✗" in page


def test_the_backtest_line_is_quoted_from_the_artifact_in_german_format():
    backtest = {
        "seasons": ["2223", "2324"],
        "schemes": {"flat": {"summary": {"n_bets": 4540, "yield": -0.0878,
                                          "yield_ci": [-0.128, -0.048]}}},
    }
    line = backtest_line(backtest)
    assert line.startswith("Backtest 2022/23 und 2023/24: 4.540 Papier-Wetten")
    assert "−8,8 %" in line
