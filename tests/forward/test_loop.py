"""End-to-end forward-loop behaviour on fake providers — no network, no real money.

The three properties that make a forward track record worth anything: it never bets after
kickoff, it settles exactly once, and running it again changes nothing.
"""

from __future__ import annotations

import pandas as pd
import pytest

from matchscout.data.fakes import FakeFixtureProvider, FakeProvider
from matchscout.data.schema import MATCH_COLUMNS, ODDS_COLUMNS
from matchscout.forward.ledger import NO_ODDS, PENDING, SETTLED, VOID, current_bets, load_events
from matchscout.forward.loop import ForwardConfig, run_forward

COMP = "E0"
SEASON = "2627"
TEAMS = ["Ajax", "Brest", "Celta", "Derby", "Everton", "Fulham"]


def _match_id(date: str, home: str, away: str) -> str:
    return f"{COMP}:{SEASON}:{pd.Timestamp(date).strftime('%Y%m%d')}:{home}:{away}"


def _history(n_rounds: int = 18) -> pd.DataFrame:
    """A synthetic played season: Ajax strong, Fulham weak, enough rows to clear the burn-in."""
    strength = {team: 3 - i * 0.5 for i, team in enumerate(TEAMS)}
    rows = []
    day = pd.Timestamp("2026-01-10")
    for r in range(n_rounds):
        for i in range(0, len(TEAMS), 2):
            home, away = TEAMS[i], TEAMS[(i + 1 + r) % len(TEAMS)]
            if home == away:
                continue
            date = day + pd.Timedelta(days=3 * r)
            hg = max(0, int(strength[home]) + (r % 2))
            ag = max(0, int(strength[away]))
            rows.append(
                {
                    "match_id": _match_id(str(date.date()), home, away),
                    "competition": COMP,
                    "season": SEASON,
                    "date": date,
                    "kickoff_utc": pd.NaT,
                    "home": home,
                    "away": away,
                    "ft_home_goals": hg,
                    "ft_away_goals": ag,
                    "status": "played",
                    "timestamp_event": date,
                    "timestamp_known": pd.NaT,
                }
            )
    return pd.DataFrame(rows, columns=MATCH_COLUMNS)


def _fixture(date: str, home: str, away: str, kickoff: str | None = None) -> pd.DataFrame:
    stamp = pd.Timestamp(kickoff or f"{date} 15:00")
    return pd.DataFrame(
        [
            {
                "match_id": _match_id(date, home, away),
                "competition": COMP,
                "season": SEASON,
                "date": pd.Timestamp(date),
                "kickoff_utc": pd.NaT,
                "home": home,
                "away": away,
                "ft_home_goals": pd.NA,
                "ft_away_goals": pd.NA,
                "status": "scheduled",
                "timestamp_event": stamp,
                "timestamp_known": pd.NaT,
            }
        ],
        columns=MATCH_COLUMNS,
    )


def _odds(match_id: str, prices: dict[str, float], *, book="B365", closing=False) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": match_id,
                "market": "1x2",
                "selection": selection,
                "book": book,
                "odds": price,
                "is_closing": closing,
                "collected_at": pd.NaT,
            }
            for selection, price in prices.items()
        ],
        columns=ODDS_COLUMNS,
    )


def _empty(columns):
    return pd.DataFrame({c: pd.Series(dtype="object") for c in columns})


# Generous home price on a strong team: the model will see an edge and bet it.
GENEROUS = {"H": 6.0, "D": 4.0, "A": 4.5}
CONFIG = ForwardConfig(
    competitions=(COMP,), season=SEASON, history_seasons=(SEASON,), min_train=30
)


@pytest.fixture
def paths(tmp_path):
    return {
        "bets_path": tmp_path / "bets.jsonl",
        "snapshots_path": tmp_path / "snapshots.jsonl",
        "trial_log_path": tmp_path / "trial_log.jsonl",
    }


def _providers(history: pd.DataFrame, fixtures: pd.DataFrame, fixture_odds: pd.DataFrame):
    return (
        FakeProvider(
            matches={(COMP, SEASON): history},
            odds={(COMP, SEASON): _empty(ODDS_COLUMNS)},
        ),
        FakeFixtureProvider({(COMP, SEASON): (fixtures, fixture_odds)}),
    )


def test_a_run_places_bets_and_leaves_them_pending(paths):
    fixtures = _fixture("2026-04-01", "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))

    out = run_forward(
        now=pd.Timestamp("2026-03-30T09:00:00"),
        history=history,
        fixtures=fixture_provider,
        config=CONFIG,
        **paths,
    )
    assert out["n_placed"] >= 1
    bets = current_bets(paths["bets_path"])
    assert set(bets["status"]) == {PENDING}
    assert (bets["stake"] == 10.0).all()
    assert bets["timestamp_known"].iloc[0] == "2026-03-30T09:00:00"
    assert out["record"]["n_bets"] == 0  # nothing settled yet — no result is claimed early


def test_running_twice_on_the_same_day_changes_nothing(paths):
    fixtures = _fixture("2026-04-01", "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))
    kwargs = dict(history=history, fixtures=fixture_provider, config=CONFIG, **paths)

    first = run_forward(now=pd.Timestamp("2026-03-30T09:00:00"), **kwargs)
    events_after_first = load_events(paths["bets_path"])
    second = run_forward(now=pd.Timestamp("2026-03-30T21:00:00"), **kwargs)

    assert first["n_placed"] >= 1
    assert second["n_placed"] == 0
    assert load_events(paths["bets_path"]) == events_after_first


def test_a_fixture_that_already_kicked_off_is_never_bet(paths):
    fixtures = _fixture("2026-04-01", "Ajax", "Fulham", kickoff="2026-04-01 15:00")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))

    out = run_forward(
        now=pd.Timestamp("2026-04-01T16:30:00"),  # 90 minutes after the whistle
        history=history,
        fixtures=fixture_provider,
        config=CONFIG,
        **paths,
    )
    assert out["n_placed"] == 0
    assert out["n_no_odds"] == 0


def test_a_fixture_inside_the_lead_time_is_not_bet(paths):
    # The source states kickoff in UK local time with no offset; a bet placed an hour before
    # kickoff could in truth be an hour after it. The lead-time margin forbids the situation.
    fixtures = _fixture("2026-04-01", "Ajax", "Fulham", kickoff="2026-04-01 15:00")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))

    out = run_forward(
        now=pd.Timestamp("2026-04-01T14:00:00"),  # 1h before kickoff, inside the 2h margin
        history=history,
        fixtures=fixture_provider,
        config=CONFIG,
        **paths,
    )
    assert out["n_placed"] == 0


def test_a_played_fixture_settles_exactly_once_and_carries_clv(paths):
    date = "2026-04-01"
    fixtures = _fixture(date, "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))
    kwargs = dict(config=CONFIG, **paths)

    run_forward(
        now=pd.Timestamp("2026-03-30T09:00:00"),
        history=history,
        fixtures=fixture_provider,
        **kwargs,
    )

    # The fixture is played: Ajax wins 2-0, and the closing line is available for CLV.
    result = fixtures.copy()
    result["ft_home_goals"] = 2
    result["ft_away_goals"] = 0
    result["status"] = "played"
    settled_history = FakeProvider(
        matches={(COMP, SEASON): pd.concat([_history(), result], ignore_index=True)},
        odds={
            (COMP, SEASON): _odds(
                mid, {"H": 4.5, "D": 4.0, "A": 1.9}, book="PS", closing=True
            )
        },
    )
    after = run_forward(
        now=pd.Timestamp("2026-04-02T09:00:00"),
        history=settled_history,
        fixtures=FakeFixtureProvider({}),
        **kwargs,
    )
    assert after["n_settled_now"] >= 1

    bets = current_bets(paths["bets_path"])
    home_bet = bets[bets["selection"] == "H"].iloc[0]
    assert home_bet["status"] == SETTLED
    assert bool(home_bet["won"])
    assert home_bet["pnl"] == pytest.approx(10.0 * (6.0 - 1.0))
    assert home_bet["clv_book"] == "PS"
    assert home_bet["clv"] > 0  # took 6.0 on a selection the market closed at 4.5

    again = run_forward(
        now=pd.Timestamp("2026-04-03T09:00:00"),
        history=settled_history,
        fixtures=FakeFixtureProvider({}),
        **kwargs,
    )
    assert again["n_settled_now"] == 0
    assert again["record"]["n_bets"] == after["record"]["n_bets"]


def test_clv_falls_back_to_the_next_book_and_says_which(paths):
    date = "2026-04-01"
    fixtures = _fixture(date, "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))
    kwargs = dict(config=CONFIG, **paths)
    run_forward(
        now=pd.Timestamp("2026-03-30T09:00:00"),
        history=history,
        fixtures=fixture_provider,
        **kwargs,
    )

    result = fixtures.copy()
    result["ft_home_goals"], result["ft_away_goals"], result["status"] = 2, 0, "played"
    no_pinnacle = FakeProvider(
        matches={(COMP, SEASON): pd.concat([_history(), result], ignore_index=True)},
        # Pinnacle is gone from the current-season files; Avg closing is what is left.
        odds={
            (COMP, SEASON): _odds(
                mid, {"H": 4.4, "D": 4.1, "A": 1.95}, book="Avg", closing=True
            )
        },
    )
    run_forward(
        now=pd.Timestamp("2026-04-02T09:00:00"),
        history=no_pinnacle,
        fixtures=FakeFixtureProvider({}),
        **kwargs,
    )
    bets = current_bets(paths["bets_path"])
    assert bets[bets["selection"] == "H"].iloc[0]["clv_book"] == "Avg"


def test_an_unpriced_fixture_is_recorded_not_invented(paths):
    fixtures = _fixture("2026-04-01", "Ajax", "Fulham")
    history, fixture_provider = _providers(_history(), fixtures, _empty(ODDS_COLUMNS))

    out = run_forward(
        now=pd.Timestamp("2026-03-30T09:00:00"),
        history=history,
        fixtures=fixture_provider,
        config=CONFIG,
        **paths,
    )
    assert out["n_placed"] == 0
    assert out["n_no_odds"] == 1
    row = current_bets(paths["bets_path"]).iloc[0]
    assert row["status"] == NO_ODDS
    assert row["stake"] == 0.0
    assert row["odds_taken"] is None  # no price existed, so none is written


def test_an_unpriced_fixture_can_still_be_bet_once_a_price_appears(paths):
    fixtures = _fixture("2026-04-01", "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, no_prices = _providers(_history(), fixtures, _empty(ODDS_COLUMNS))
    run_forward(
        now=pd.Timestamp("2026-03-29T09:00:00"),
        history=history,
        fixtures=no_prices,
        config=CONFIG,
        **paths,
    )
    _, with_prices = _providers(_history(), fixtures, _odds(mid, GENEROUS))
    out = run_forward(
        now=pd.Timestamp("2026-03-30T09:00:00"),
        history=history,
        fixtures=with_prices,
        config=CONFIG,
        **paths,
    )
    assert out["n_placed"] >= 1


def test_a_fixture_that_never_produced_a_result_is_voided_not_forgotten(paths):
    fixtures = _fixture("2026-04-01", "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))
    kwargs = dict(config=CONFIG, **paths)
    run_forward(
        now=pd.Timestamp("2026-03-30T09:00:00"),
        history=history,
        fixtures=fixture_provider,
        **kwargs,
    )
    out = run_forward(  # 20 days later, still no result: postponed or renamed
        now=pd.Timestamp("2026-04-21T09:00:00"),
        history=history,
        fixtures=FakeFixtureProvider({}),
        **kwargs,
    )
    assert out["n_voided_now"] >= 1
    voided = current_bets(paths["bets_path"])
    assert (voided[voided["status"] == VOID]["pnl"] == 0.0).all()


def test_the_config_is_logged_as_a_trial_once_not_once_per_run(paths):
    from matchscout.evaluation.trial_log import load_trials

    fixtures = _fixture("2026-04-01", "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))
    kwargs = dict(history=history, fixtures=fixture_provider, config=CONFIG, **paths)

    first = run_forward(now=pd.Timestamp("2026-03-30T09:00:00"), **kwargs)
    second = run_forward(now=pd.Timestamp("2026-03-31T09:00:00"), **kwargs)
    assert first["config_newly_logged"] is True
    assert second["config_newly_logged"] is False

    trials = load_trials(paths["trial_log_path"])
    assert len([t for t in trials if t["kind"] == "forward"]) == 1

    changed = ForwardConfig(
        competitions=(COMP,), season=SEASON, history_seasons=(SEASON,), min_train=30,
        threshold=0.20,
    )
    run_forward(
        now=pd.Timestamp("2026-04-01T09:00:00"),
        history=history,
        fixtures=fixture_provider,
        config=changed,
        **paths,
    )
    assert len([t for t in load_trials(paths["trial_log_path"]) if t["kind"] == "forward"]) == 2


def test_every_run_appends_a_snapshot(paths):
    from matchscout.forward.ledger import load_snapshots

    fixtures = _fixture("2026-04-01", "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(), fixtures, _odds(mid, GENEROUS))
    kwargs = dict(history=history, fixtures=fixture_provider, config=CONFIG, **paths)

    run_forward(now=pd.Timestamp("2026-03-30T09:00:00"), **kwargs)
    run_forward(now=pd.Timestamp("2026-03-31T09:00:00"), **kwargs)
    snaps = load_snapshots(paths["snapshots_path"])
    assert [s["run_id"] for s in snaps] == ["2026-03-30", "2026-03-31"]
    assert snaps[0]["bankroll"] == 1000.0
    assert snaps[0]["n_pending"] >= 1
    assert snaps[0]["yield"] is None  # nothing settled: no yield is claimed, not a zero


def test_burn_in_skips_a_competition_instead_of_guessing(paths):
    fixtures = _fixture("2026-04-01", "Ajax", "Fulham")
    mid = fixtures.iloc[0]["match_id"]
    history, fixture_provider = _providers(_history(n_rounds=2), fixtures, _odds(mid, GENEROUS))

    out = run_forward(
        now=pd.Timestamp("2026-03-30T09:00:00"),
        history=history,
        fixtures=fixture_provider,
        config=CONFIG,
        **paths,
    )
    assert out["n_placed"] == 0
    assert out["skipped_competitions"][0]["competition"] == COMP
    assert "burn-in" in out["skipped_competitions"][0]["reason"]
