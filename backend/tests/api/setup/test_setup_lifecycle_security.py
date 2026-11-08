"""Security regression tests for unauthenticated setup mutations."""

from unittest.mock import patch

import pytest
from jose import jwt
from sqlalchemy import select, text

from app.core import database as app_database
from app.models.peer import Peer
from app.models.server import Server
from app.models.settings import GlobalSettings
from app.models.user import User


MUTATIONS = [
    ("reset", None),
    ("configure-database", {"database_type": "sqlite", "database_url": "sqlite+aiosqlite:///:memory:"}),
    ("initialize", {"username": "attacker", "email": "attacker@example.com", "password": "password123"}),
    ("configure-globals", {"secret_key": "a" * 40, "disable_auth": True}),
    ("configure-auth", {"skip": True}),
    ("update-progress", {"current_step": "database"}),
    ("create-server", {"name": "attacker", "endpoint": "vpn.example.com", "listen_port": 51820, "ipv4_address": "10.0.0.1/24"}),
    ("create-peer", {"server_id": 1, "name": "attacker"}),
    ("complete", None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS)
async def test_should_reject_mutations_after_setup_completion(
    endpoint, payload, api_client, db_session, seeded_db, isolated_config, fake_engine_switch
):
    isolated_config.write_text('{"database": {"type": "sqlite", "url": "sqlite://"}}')

    response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 403
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.setup_completed is True
    assert settings.disable_auth is False
    assert settings.secret_key != "a" * 40
    assert settings.setup_current_step is None
    assert len((await db_session.execute(select(User))).scalars().all()) == 2
    assert (await db_session.execute(select(Server))).scalars().all() == []
    assert (await db_session.execute(select(Peer))).scalars().all() == []
    assert isolated_config.exists()
    assert not fake_engine_switch.reinit_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS)
async def test_should_reject_mutations_when_database_check_fails(
    endpoint, payload, api_client, isolated_config, fake_engine_switch
):
    with patch.object(app_database, "AsyncSessionLocal", side_effect=RuntimeError("database unavailable")):
        response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 503
    assert not isolated_config.exists()
    assert not fake_engine_switch.reinit_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS)
async def test_should_reject_mutations_when_settings_query_fails(
    endpoint, payload, api_client, api_db, isolated_config, fake_engine_switch
):
    async with api_db.engine.begin() as conn:
        await conn.execute(text("DROP TABLE global_settings"))

    response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 503
    assert not isolated_config.exists()
    assert not fake_engine_switch.reinit_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS)
async def test_should_reject_mutations_when_config_exists_but_engine_is_absent(
    endpoint, payload, api_client, isolated_config, fake_engine_switch
):
    isolated_config.write_text('{"database": {"type": "sqlite", "url": "sqlite://"}}')
    with patch.object(app_database, "engine", None), patch.object(app_database, "AsyncSessionLocal", None):
        response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 503
    assert isolated_config.exists()
    assert not fake_engine_switch.reinit_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS)
async def test_should_reject_mutations_when_session_factory_is_missing(
    endpoint, payload, api_client, isolated_config, fake_engine_switch
):
    with patch.object(app_database, "AsyncSessionLocal", None):
        response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 503
    assert not isolated_config.exists()
    assert not fake_engine_switch.reinit_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS)
async def test_should_reject_mutations_when_engine_is_missing_but_factory_exists(
    endpoint, payload, api_client, isolated_config, fake_engine_switch
):
    with patch.object(app_database, "engine", None):
        response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 503
    assert not isolated_config.exists()
    assert not fake_engine_switch.reinit_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS[:2])
async def test_should_allow_database_step_and_reset_on_fresh_install(
    endpoint, payload, api_client, isolated_config, fake_engine_switch
):
    with patch.object(app_database, "engine", None), patch.object(app_database, "AsyncSessionLocal", None):
        response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS[2:])
async def test_should_reject_database_dependent_steps_on_fresh_install(
    endpoint, payload, api_client, isolated_config
):
    with patch.object(app_database, "engine", None), patch.object(app_database, "AsyncSessionLocal", None):
        response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS)
async def test_should_require_admin_after_account_creation(
    endpoint, payload, api_client, db_session, seeded_db, isolated_config, fake_engine_switch
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    settings.disable_auth = True
    await db_session.commit()

    response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)

    assert response.status_code == 401
    await db_session.refresh(settings)
    assert settings.setup_completed is False
    assert not fake_engine_switch.reinit_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", MUTATIONS)
async def test_should_reject_standard_user_during_setup(
    endpoint, payload, api_client, db_session, seeded_db, user_headers, isolated_config, fake_engine_switch
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    await db_session.commit()

    response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload, headers=user_headers)

    assert response.status_code == 403
    assert not fake_engine_switch.reinit_calls


@pytest.mark.asyncio
async def test_should_sign_in_and_continue_setup_after_admin_created(api_client, db_session, isolated_config):
    payload = {"username": "firstadmin", "email": "firstadmin@example.com", "password": "password123"}
    assert api_client.post("/api/v1/setup/initialize", json=payload).status_code == 200
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    assert settings.secret_key != "temporary-key-will-be-replaced"
    assert len(settings.secret_key) >= 32

    forged = jwt.encode({"sub": "firstadmin"}, "temporary-key-will-be-replaced", algorithm="HS256")
    assert api_client.post("/api/v1/setup/update-progress", json={"current_step": "auth"}, headers={"Authorization": f"Bearer {forged}"}).status_code == 401

    login = api_client.post("/api/v1/auth/token", data={"username": "firstadmin", "password": "password123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = api_client.post("/api/v1/setup/configure-globals", json={"secret_key": "z" * 40}, headers=headers)
    assert response.status_code == 200
    assert api_client.post("/api/v1/setup/configure-auth", json={"skip": True}, headers=headers).status_code == 401
    login = api_client.post("/api/v1/auth/token", data={"username": "firstadmin", "password": "password123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert api_client.post("/api/v1/setup/configure-auth", json={"skip": True}, headers=headers).status_code == 200


@pytest.mark.asyncio
async def test_should_replace_old_temporary_key_when_initializing(api_client, db_session, isolated_config):
    db_session.add(GlobalSettings(secret_key="temporary-key-will-be-replaced", backup_dir="./b"))
    await db_session.commit()
    response = api_client.post("/api/v1/setup/initialize", json={"username": "firstadmin", "email": "firstadmin@example.com", "password": "password123"})
    assert response.status_code == 200
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.secret_key != "temporary-key-will-be-replaced"


@pytest.mark.asyncio
async def test_should_not_persist_failed_database_choice(api_client, api_db, isolated_config, tmp_path):
    bad_url = f"sqlite+aiosqlite:///{tmp_path / 'missing' / 'database.db'}"
    response = api_client.post("/api/v1/setup/configure-database", json={"database_type": "sqlite", "database_url": bad_url})
    assert response.status_code == 500
    assert not isolated_config.exists()
    assert app_database.engine is api_db.engine
    assert app_database.AsyncSessionLocal is api_db.sessionmaker
    assert api_client.post("/api/v1/setup/update-progress", json={"current_step": "database"}).status_code == 200


@pytest.mark.asyncio
async def test_should_not_switch_to_empty_database_after_admin_creation(
    api_client, db_session, seeded_db, admin_headers, isolated_config
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    await db_session.commit()
    response = api_client.post(
        "/api/v1/setup/configure-database",
        json={"database_type": "sqlite", "database_url": "sqlite+aiosqlite:///:memory:"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert not isolated_config.exists()


@pytest.mark.asyncio
async def test_should_allow_authenticated_admin_when_auth_is_disabled(
    api_client, db_session, seeded_db, admin_headers, isolated_config
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    settings.disable_auth = True
    await db_session.commit()
    response = api_client.post(
        "/api/v1/setup/update-progress", json={"current_step": "auth"}, headers=admin_headers
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_should_fail_closed_for_legacy_predictable_key_with_admin(
    api_client, db_session, seeded_db, isolated_config
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    settings.secret_key = "temporary-key-will-be-replaced"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "exp": 4102444800}, settings.secret_key, algorithm="HS256")
    response = api_client.post(
        "/api/v1/setup/update-progress", json={"current_step": "auth"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("completed,disable_auth", [(False, False), (False, True), (True, False), (True, True)])
async def test_should_reject_legacy_key_for_normal_authentication(
    completed, disable_auth, api_client, db_session, seeded_db, isolated_config
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = completed
    settings.disable_auth = disable_auth
    settings.secret_key = "temporary-key-will-be-replaced"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "exp": 4102444800}, settings.secret_key, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    assert api_client.get("/api/v1/auth/users", headers=headers).status_code == 503
    assert api_client.get("/api/v1/auth/users").status_code == 503
    assert api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).status_code == 503
    assert api_client.get("/api/v1/logs/download", params={"token": token}).status_code == 503


@pytest.mark.asyncio
async def test_should_reject_existing_websocket_authentication_for_legacy_key(api_client, db_session, seeded_db, isolated_config):
    from fastapi import HTTPException
    from app.api.ws import authenticate
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    settings.secret_key = "temporary-key-will-be-replaced"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "exp": 4102444800}, settings.secret_key, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        await authenticate(token)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_should_retry_after_failed_fresh_database_choice(api_client, isolated_config, tmp_path):
    from unittest.mock import AsyncMock

    bad_url = f"sqlite+aiosqlite:///{tmp_path / 'missing' / 'db.sqlite'}"
    good_url = f"sqlite+aiosqlite:///{tmp_path / 'good.sqlite'}"
    with patch.object(app_database, "engine", None), \
         patch.object(app_database, "AsyncSessionLocal", None), \
         patch("app.main.start_background_monitors", new_callable=AsyncMock):
        response = api_client.post("/api/v1/setup/configure-database", json={"database_type": "sqlite", "database_url": bad_url})
        assert response.status_code == 500
        assert not isolated_config.exists()
        assert app_database.engine is None
        response = api_client.post("/api/v1/setup/configure-database", json={"database_type": "sqlite", "database_url": good_url})
        assert response.status_code == 200
        assert isolated_config.exists()
        await app_database.engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,payload", [
    MUTATIONS[3], MUTATIONS[4], MUTATIONS[6], MUTATIONS[7], MUTATIONS[8],
])
async def test_should_require_account_before_later_setup_steps(endpoint, payload, api_client, db_session, isolated_config):
    response = api_client.post(f"/api/v1/setup/{endpoint}", json=payload)
    assert response.status_code == 409
    assert (await db_session.execute(select(User))).scalars().all() == []
    assert (await db_session.execute(select(GlobalSettings))).scalars().all() == []


@pytest.mark.asyncio
async def test_should_not_create_implicit_admin_when_auth_disabled_during_setup(api_client, db_session, isolated_config):
    db_session.add(GlobalSettings(secret_key="k" * 40, backup_dir="./b", disable_auth=True, setup_completed=False))
    await db_session.commit()
    response = api_client.get("/api/v1/auth/users")
    assert response.status_code == 401
    assert (await db_session.execute(select(User))).scalars().all() == []


@pytest.mark.asyncio
async def test_should_require_credentials_when_auth_disabled_but_setup_incomplete(api_client, db_session, seeded_db, isolated_config):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    settings.disable_auth = True
    await db_session.commit()
    assert api_client.get("/api/v1/auth/users").status_code == 401


@pytest.mark.asyncio
async def test_should_allow_real_docker_sqlite_setup_reset_and_retry(api_client, api_db, tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    from app.core.config_loader import ConfigLoader, config_loader
    from app.core.database import get_db
    from app.main import app

    db_path = tmp_path / "data" / "linguard.db"
    config_path = tmp_path / "data" / "linguard.config.json"
    monkeypatch.setenv("LINGUARD_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("LINGUARD_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(ConfigLoader, "DEFAULT_CONFIG_PATH", tmp_path / "legacy.json")
    monkeypatch.setattr(config_loader, "config_path", config_path)
    monkeypatch.setattr(config_loader, "_persistent_override", True)
    override = app.dependency_overrides.pop(get_db)
    try:
        with patch.object(app_database, "engine", None), \
             patch.object(app_database, "AsyncSessionLocal", None), \
             patch("app.main.start_background_monitors", new_callable=AsyncMock), \
             patch("app.main.stop_background_monitors", new_callable=AsyncMock):
            data = {"database_type": "sqlite", "database_url": "./data/linguard.db"}
            response = api_client.post("/api/v1/setup/configure-database", json=data)
            assert response.status_code == 200, response.text
            assert db_path.exists() and config_path.exists()
            assert api_client.post("/api/v1/setup/reset").status_code == 200
            assert not config_path.exists()
            assert not db_path.exists()
            response = api_client.post("/api/v1/setup/configure-database", json=data)
            assert response.status_code == 200, response.text
            assert db_path.exists() and config_path.exists()
            await app_database.engine.dispose()
    finally:
        app.dependency_overrides[get_db] = override


@pytest.mark.asyncio
async def test_should_remove_new_docker_database_if_saving_config_fails(api_client, tmp_path, monkeypatch):
    from app.core.config_loader import ConfigLoader, config_loader

    db_path = tmp_path / "data" / "linguard.db"
    monkeypatch.setenv("LINGUARD_SQLITE_PATH", str(db_path))
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "data" / "config.json")
    monkeypatch.setattr(config_loader, "_persistent_override", True)
    monkeypatch.setattr(ConfigLoader, "DEFAULT_CONFIG_PATH", tmp_path / "legacy.json")
    with patch.object(app_database, "engine", None), \
         patch.object(app_database, "AsyncSessionLocal", None), \
         patch.object(config_loader, "save", side_effect=OSError("disk full")):
        response = api_client.post("/api/v1/setup/configure-database", json={"database_type": "sqlite", "database_url": "./data/linguard.db"})
    assert response.status_code == 500
    assert not db_path.exists()
