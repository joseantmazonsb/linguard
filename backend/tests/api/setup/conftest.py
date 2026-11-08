"""Fixtures local to the setup-wizard API tests.

The setup endpoints write ``linguard.config.json`` next to the backend package
and switch the process-wide database engine. Every test here therefore runs
with the config file redirected into ``tmp_path`` and with the two true
external boundaries of the wizard (engine re-init / schema creation and the
background monitors) replaced by recorders.
"""

from unittest.mock import patch

import pytest

from app.core import database as app_database
from app.core.config_loader import config_loader


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the global config loader at a throw-away directory."""
    path = tmp_path / "linguard.config.json"
    monkeypatch.setattr(config_loader, "config_path", path)
    return path


@pytest.fixture
def fake_engine_switch():
    """Use a real isolated candidate engine and record its requested URL.

    Returns a recorder so tests can assert exactly which database URL the
    wizard asked the engine to switch to, and whether the schema creation and
    monitor start were triggered.
    """

    class Recorder:
        def __init__(self):
            self.reinit_calls = []
            self.init_db_calls = 0
            self.monitor_starts = 0

    recorder = Recorder()

    build_engine = app_database._build_engine

    def _build(url):
        recorder.reinit_calls.append(url)
        return build_engine("sqlite+aiosqlite://")

    async def _start_monitors():
        recorder.monitor_starts += 1

    with patch.object(app_database, "_build_engine", _build), \
         patch("app.main.start_background_monitors", _start_monitors):
        yield recorder
