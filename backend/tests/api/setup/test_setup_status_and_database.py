"""Tests for the setup wizard's status, reset and database steps."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core import database as app_database
from app.models.settings import GlobalSettings

STATUS_URL = "/api/v1/setup/status"
RESET_URL = "/api/v1/setup/reset"
CONFIGURE_DB_URL = "/api/v1/setup/configure-database"


async def _add_settings(session, **overrides):
    values = dict(
        secret_key="k" * 40,
        backup_dir="./backups",
        setup_completed=False,
        setup_current_step="globals",
    )
    values.update(overrides)
    row = GlobalSettings(**values)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@pytest.mark.asyncio
async def test_should_report_requires_setup_when_engine_is_absent(api_client):
    with patch.object(app_database, "engine", None):
        response = api_client.get(STATUS_URL)

    assert response.status_code == 200
    assert response.json() == {
        "setup_completed": False,
        "requires_setup": True,
        "current_step": None,
    }


@pytest.mark.asyncio
async def test_should_report_requires_setup_when_no_settings_row_exists(api_client, db_session):
    response = api_client.get(STATUS_URL)

    assert response.status_code == 200
    assert response.json()["requires_setup"] is True
    assert response.json()["current_step"] is None

    rows = (await db_session.execute(select(GlobalSettings))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_should_return_current_step_when_setup_is_in_progress(api_client, db_session):
    await _add_settings(db_session, setup_current_step="auth")

    response = api_client.get(STATUS_URL)

    assert response.status_code == 200
    assert response.json() == {
        "setup_completed": False,
        "requires_setup": True,
        "current_step": "auth",
    }


@pytest.mark.asyncio
async def test_should_report_completed_when_settings_marked_complete(api_client, db_session):
    await _add_settings(db_session, setup_completed=True, setup_current_step=None)

    response = api_client.get(STATUS_URL)

    assert response.json() == {
        "setup_completed": True,
        "requires_setup": False,
        "current_step": None,
    }


@pytest.mark.asyncio
async def test_should_fall_back_to_requires_setup_when_database_query_fails(api_client):
    def _boom():
        raise RuntimeError("database is down")

    with patch.object(app_database, "AsyncSessionLocal", _boom):
        response = api_client.get(STATUS_URL)

    assert response.status_code == 200
    assert response.json()["requires_setup"] is True


@pytest.mark.asyncio
async def test_should_drop_tables_delete_config_and_stop_monitors_when_reset(
    api_client, db_session, isolated_config, seeded_db
):
    isolated_config.write_text('{"database": {"type": "sqlite", "url": "sqlite://"}}')
    stop_calls = []

    async def _stop():
        stop_calls.append(True)

    with patch("app.main.stop_background_monitors", _stop):
        response = api_client.post(RESET_URL)

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Setup reset. Ready to start fresh.",
    }
    assert stop_calls == [True]
    assert not isolated_config.exists()
    assert app_database.engine is None
    assert app_database.AsyncSessionLocal is None

    # Tables were dropped: the seeded settings row is gone from disk.
    from sqlalchemy import create_engine, text

    sync_engine = create_engine(f"sqlite:///{isolated_config.parent / 'api_test.db'}")
    with sync_engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    assert ("global_settings",) not in tables


@pytest.mark.asyncio
async def test_should_skip_config_removal_when_no_config_file_exists(api_client, isolated_config):
    assert not isolated_config.exists()

    response = api_client.post(RESET_URL)

    assert response.status_code == 200
    assert not isolated_config.exists()


@pytest.mark.asyncio
async def test_should_continue_reset_when_monitors_cannot_be_stopped(api_client):
    async def _boom():
        raise RuntimeError("monitor stuck")

    with patch("app.main.stop_background_monitors", _boom):
        response = api_client.post(RESET_URL)

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_should_return_500_when_reset_cannot_drop_tables(api_client):
    class BrokenEngine:
        def begin(self):
            raise RuntimeError("engine is wedged")

    with patch.object(app_database, "engine", BrokenEngine()):
        response = api_client.post(RESET_URL)

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to reset setup: engine is wedged"


@pytest.mark.asyncio
async def test_should_convert_relative_sqlite_path_when_configure_database(
    api_client, isolated_config, fake_engine_switch, tmp_path, monkeypatch
):
    monkeypatch.delenv("LINGUARD_SQLITE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    response = api_client.post(
        CONFIGURE_DB_URL,
        json={"database_type": "sqlite", "database_url": "./data/linguard.db"},
    )

    expected_url = f"sqlite+aiosqlite:///{tmp_path / 'data' / 'linguard.db'}"
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "database_type": "sqlite",
        "database_url": expected_url,
        "message": "SQLITE database configured successfully.",
        "requires_restart": False,
    }
    assert fake_engine_switch.reinit_calls == [expected_url]
    assert fake_engine_switch.init_db_calls == 1
    assert fake_engine_switch.monitor_starts == 1
    # The chosen backend is persisted for the next startup.
    assert isolated_config.exists()
    from app.core.config_loader import config_loader

    assert config_loader.get_database_type() == "sqlite"
    assert config_loader.get_database_url() == expected_url


@pytest.mark.asyncio
async def test_should_use_env_override_path_when_configure_database(
    api_client, isolated_config, fake_engine_switch, tmp_path, monkeypatch
):
    pinned = tmp_path / "volume" / "linguard.db"
    monkeypatch.setenv("LINGUARD_SQLITE_PATH", str(pinned))

    response = api_client.post(
        CONFIGURE_DB_URL,
        json={"database_type": "sqlite", "database_url": "some/relative.db"},
    )

    expected_url = f"sqlite+aiosqlite:///{pinned}"
    assert response.status_code == 200
    assert response.json()["database_url"] == expected_url
    assert fake_engine_switch.reinit_calls == [expected_url]


@pytest.mark.asyncio
async def test_should_keep_full_url_when_configure_database_given_sqlite_url(
    api_client, isolated_config, fake_engine_switch
):
    url = "sqlite+aiosqlite:////var/lib/linguard/custom.db"

    response = api_client.post(
        CONFIGURE_DB_URL, json={"database_type": "sqlite", "database_url": url}
    )

    assert response.status_code == 200
    assert response.json()["database_url"] == url
    assert fake_engine_switch.reinit_calls == [url]


@pytest.mark.asyncio
async def test_should_keep_url_verbatim_when_configure_database_postgresql(
    api_client, isolated_config, fake_engine_switch
):
    url = "postgresql+asyncpg://user:pass@db:5432/linguard"

    response = api_client.post(
        CONFIGURE_DB_URL, json={"database_type": "postgresql", "database_url": url}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "POSTGRESQL database configured successfully."
    assert fake_engine_switch.reinit_calls == [url]


@pytest.mark.asyncio
async def test_should_still_configure_database_when_monitors_fail_to_start(
    api_client, isolated_config, monkeypatch
):
    from app.core import database as db_module

    started = []
    monkeypatch.setattr(db_module, "reinit_engine", lambda url: started.append(url))
    monkeypatch.setattr(db_module, "init_db", AsyncMock())

    async def _boom():
        raise RuntimeError("monitor cannot start")

    with patch("app.main.start_background_monitors", _boom):
        response = api_client.post(
            CONFIGURE_DB_URL,
            json={"database_type": "sqlite", "database_url": "sqlite+aiosqlite:///:memory:"},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert started == ["sqlite+aiosqlite:///:memory:"]


@pytest.mark.asyncio
async def test_should_return_500_when_configure_database_engine_init_fails(
    api_client, isolated_config, monkeypatch
):
    from app.core import database as db_module

    def _fail(url):
        raise RuntimeError("cannot connect")

    monkeypatch.setattr(db_module, "reinit_engine", _fail)

    response = api_client.post(
        CONFIGURE_DB_URL,
        json={"database_type": "sqlite", "database_url": "sqlite+aiosqlite:///:memory:"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to configure database: RuntimeError: cannot connect"


@pytest.mark.asyncio
async def test_should_reject_unknown_database_type_when_configure_database(api_client):
    response = api_client.post(
        CONFIGURE_DB_URL, json={"database_type": "oracle", "database_url": "oracle://x"}
    )

    assert response.status_code == 422
    assert "body.database_type" in response.json()["errors"]
