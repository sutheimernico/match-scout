import os

from matchscout.config import football_data_api_key, load_env


def test_load_env_sets_vars(tmp_path, monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("# comment\nFOOTBALL_DATA_API_KEY=abc123\nEMPTYLINE=\n")
    load_env(env)
    assert os.environ["FOOTBALL_DATA_API_KEY"] == "abc123"
    assert football_data_api_key() == "abc123"


def test_load_env_does_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "already-set")
    env = tmp_path / ".env"
    env.write_text("FOOTBALL_DATA_API_KEY=from-file\n")
    load_env(env)
    assert os.environ["FOOTBALL_DATA_API_KEY"] == "already-set"


def test_load_env_missing_file_is_noop(tmp_path):
    load_env(tmp_path / "nope.env")  # must not raise
