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
    """Patch reinit_engine / init_db / start_background_monitors.

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

    def _reinit(url):
        recorder.reinit_calls.append(url)

    async def _init_db():
        recorder.init_db_calls += 1

    async def _start_monitors():
        recorder.monitor_starts += 1

    with patch.object(app_database, "reinit_engine", _reinit), \
         patch.object(app_database, "init_db", _init_db), \
         patch("app.main.start_background_monitors", _start_monitors):
        yield recorder
