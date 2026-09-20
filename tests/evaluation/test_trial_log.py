"""The trial log must be append-only, stable-hashed and order-independent (council D1)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from matchscout.evaluation.trial_log import (
    append_trial,
    load_trials,
    n_distinct_configs,
    trial_id,
)

CONFIG = {"threshold": 0.05, "min_train": 80, "half_life_days": 180.0, "book": "B365"}
METRICS = {"n_bets": 971, "yield": -0.047}


def test_trial_id_is_key_order_independent():
    reordered = dict(reversed(list(CONFIG.items())))
    assert trial_id(CONFIG) == trial_id(reordered)


def test_trial_id_changes_with_any_knob():
    assert trial_id(CONFIG) != trial_id({**CONFIG, "threshold": 0.06})


def test_append_is_append_only_and_round_trips(tmp_path):
    path = tmp_path / "nested" / "trial_log.jsonl"
    first = append_trial(path, config=CONFIG, metrics=METRICS, code_version="abc1234")
    append_trial(
        path, config={**CONFIG, "threshold": 0.10}, metrics=METRICS, code_version="abc1234"
    )

    trials = load_trials(path)
    assert len(trials) == 2
    assert trials[0] == first
    assert trials[0]["kind"] == "backtest"
    assert trials[0]["backfilled"] is False
    assert n_distinct_configs(trials) == 2


def test_rerunning_the_same_config_logs_again_but_counts_once(tmp_path):
    path = tmp_path / "trial_log.jsonl"
    append_trial(path, config=CONFIG, metrics=METRICS, code_version="abc1234")
    append_trial(path, config=CONFIG, metrics=METRICS, code_version="abc1234")
    trials = load_trials(path)
    assert len(trials) == 2
    assert n_distinct_configs(trials) == 1


def test_entries_are_one_json_object_per_line(tmp_path):
    path = tmp_path / "trial_log.jsonl"
    append_trial(
        path,
        config=CONFIG,
        metrics=METRICS,
        kind="slice",
        code_version="abc1234",
        note="per-league cut",
        backfilled=True,
        now=pd.Timestamp("2026-07-21T10:00:00Z"),
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["kind"] == "slice"
    assert entry["backfilled"] is True
    assert entry["note"] == "per-league cut"
    assert entry["logged_at"].startswith("2026-07-21T10:00:00")


def test_load_trials_on_missing_file_is_empty(tmp_path):
    assert load_trials(tmp_path / "nope.jsonl") == []


def test_corrupt_line_fails_loudly(tmp_path):
    path = tmp_path / "trial_log.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_trials(path)
