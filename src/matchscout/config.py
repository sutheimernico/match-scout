"""Local config: load .env and read secrets from the environment.

A tiny dependency-free .env loader. Local runs call `load_env()`; CI sets the env var directly
and the loader is a no-op (no .env file present). The key is never hardcoded or logged.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | Path = ".env") -> None:
    """Populate os.environ from a KEY=VALUE .env file if present (does not overwrite set vars)."""
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def football_data_api_key() -> str | None:
    """The football-data.org token from the environment, or None if unset."""
    return os.environ.get("FOOTBALL_DATA_API_KEY")
