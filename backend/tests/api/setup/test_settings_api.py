"""Tests for GET/PUT /api/v1/settings/global."""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.settings import GlobalSettings
from app.models.user import User

GLOBAL_URL = "/api/v1/settings/global"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/v1/settings/backup-key", None),
    ("put", "/api/v1/settings/backup-key", {"key": "new"}),
    ("put", "/api/v1/settings/backup-key/recover", {"key": "new"}),
    ("delete", "/api/v1/settings/backup-key", None),
])
async def test_key_endpoints_revalidate_admin_after_waiting_for_key_lock(auth_client, db_session, method, path, body):
    import asyncio
    from threading import Event, Thread
    from app.services.backup_crypto import key_lock, key_path

    started = Event()
    result = []
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()

    def request():
        started.set()
        result.append(getattr(auth_client, method)(path, **({"json": body} if body is not None else {})))

    async with key_lock():
        worker = Thread(target=request)
        worker.start()
        assert await asyncio.to_thread(started.wait, 2)
        await asyncio.sleep(0.25)
        admin.role = "standard"
        await db_session.commit()
    await asyncio.to_thread(worker.join, 5)
    assert not worker.is_alive()
    assert result[0].status_code == 403
    assert not key_path().exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/v1/settings/backup-key", None),
    ("put", "/api/v1/settings/backup-key", {"key": "new"}),
    ("put", "/api/v1/settings/backup-key/recover", {"key": "new"}),
    ("delete", "/api/v1/settings/backup-key", None),
])
async def test_key_endpoints_revalidate_signing_key_after_waiting(auth_client, db_session, method, path, body):
    import asyncio
    from threading import Event, Thread
    from app.services.backup_crypto import key_lock, key_path

    started = Event()
    result = []
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()

    def request():
        started.set()
        result.append(getattr(auth_client, method)(path, **({"json": body} if body is not None else {})))

    async with key_lock():
        worker = Thread(target=request)
        worker.start()
        assert await asyncio.to_thread(started.wait, 2)
        await asyncio.sleep(0.25)
        settings.secret_key = "rotated-signing-secret"
        await db_session.commit()
    await asyncio.to_thread(worker.join, 5)
    assert not worker.is_alive()
    assert result[0].status_code == 401
    assert not key_path().exists()


@pytest.mark.asyncio
async def test_key_action_rejects_deleted_user_after_waiting(auth_client, db_session):
    import asyncio
    from threading import Event, Thread
    from app.services.backup_crypto import key_lock, key_path

    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    started, result = Event(), []
    def request():
        started.set()
        result.append(auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}))
    async with key_lock():
        thread = Thread(target=request)
        thread.start()
        assert await asyncio.to_thread(started.wait, 2)
        await asyncio.sleep(0.25)
        await db_session.delete(admin)
        await db_session.commit()
    await asyncio.to_thread(thread.join, 5)
    assert result[0].status_code == 401
    assert not key_path().exists()


@pytest.mark.asyncio
async def test_key_status_rejects_revoked_auth_generation_after_waiting(auth_client, db_session):
    import asyncio
    from threading import Event, Thread
    from app.services.backup_crypto import key_lock

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    started, result = Event(), []
    def request():
        started.set()
        result.append(auth_client.get("/api/v1/settings/backup-key"))
    async with key_lock():
        thread = Thread(target=request)
        thread.start()
        assert await asyncio.to_thread(started.wait, 2)
        await asyncio.sleep(0.25)
        settings.setup_current_step = "r0000000100000000"
        await db_session.commit()
    await asyncio.to_thread(thread.join, 5)
    assert result[0].status_code == 401


@pytest.mark.asyncio
async def test_key_status_reports_no_secret_if_intent_database_write_fails(auth_client, monkeypatch):
    import app.services.backup_crypto as crypto

    crypto._set_intent()
    async def fail(*args):
        raise RuntimeError("write failed")
    monkeypatch.setattr(crypto, "persist_required", fail)
    response = auth_client.get("/api/v1/settings/backup-key")
    assert response.status_code == 500
    assert "write failed" not in response.text


@pytest.mark.asyncio
async def test_key_rotation_does_not_replace_key_after_admin_demotion(auth_client, db_session):
    import asyncio
    from threading import Event, Thread
    from app.services.backup_crypto import key_lock, key_path

    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "old"}).status_code == 200
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    started, result = Event(), []
    def request():
        started.set()
        result.append(auth_client.put("/api/v1/settings/backup-key", json={"key": "new"}))
    async with key_lock():
        thread = Thread(target=request)
        thread.start()
        assert await asyncio.to_thread(started.wait, 2)
        await asyncio.sleep(0.25)
        admin.role = "standard"
        await db_session.commit()
    await asyncio.to_thread(thread.join, 5)
    assert result[0].status_code == 403
    assert key_path().read_text() == "old"


@pytest.mark.asyncio
async def test_key_delete_does_not_clear_existing_key_after_admin_demotion(auth_client, db_session):
    import asyncio
    from threading import Event, Thread
    from app.services.backup_crypto import key_lock, key_path

    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "old"}).status_code == 200
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    started, result = Event(), []
    def request():
        started.set()
        result.append(auth_client.delete("/api/v1/settings/backup-key"))
    async with key_lock():
        thread = Thread(target=request)
        thread.start()
        assert await asyncio.to_thread(started.wait, 2)
        await asyncio.sleep(0.25)
        admin.role = "standard"
        await db_session.commit()
    await asyncio.to_thread(thread.join, 5)
    assert result[0].status_code == 403
    assert key_path().read_text() == "old"


@pytest.mark.asyncio
async def test_key_action_does_not_block_loop_while_waiting_for_key_lock(auth_client):
    import asyncio
    from app.services.backup_crypto import key_lock

    async with key_lock():
        request = asyncio.create_task(asyncio.to_thread(auth_client.get, "/api/v1/settings/backup-key"))
        await asyncio.sleep(0.15)
        assert not request.done()
    assert (await asyncio.wait_for(request, 5)).status_code == 200


@pytest.mark.asyncio
async def test_key_status_denies_revoked_admin_before_adopting_key(auth_client, db_session, monkeypatch):
    import app.api.settings as api
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import key_path

    key_path().write_text("old")
    key_path().chmod(0o600)
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    original = api._authenticate_backup_admin
    calls = 0
    async def revoke(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            admin.role = "standard"
            await db_session.commit()
        return await original(*args)
    monkeypatch.setattr(api, "_authenticate_backup_admin", revoke)
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 403
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_key_settings_revalidation_survives_enabled_expire_on_commit(api_db, seeded_db):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from starlette.requests import Request
    from jose import jwt
    from app.api.settings import BackupKeyRequest, get_backup_key_admin, put_backup_key

    sessions = async_sessionmaker(api_db.engine, expire_on_commit=True)
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "test-secret-key-for-jwt-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as session:
        admin = await get_backup_key_admin(request, session)
        result = await put_backup_key(BackupKeyRequest(key="secret"), request, session, admin)
        assert result == {"configured": True}


@pytest.mark.asyncio
async def test_key_recovery_audit_survives_expire_on_commit(api_db, seeded_db):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from starlette.requests import Request
    from jose import jwt
    from app.api.settings import BackupKeyRequest, get_backup_key_admin, put_backup_key, recover_backup_key
    from app.services.audit_logger import AuditService
    from app.services.backup_crypto import key_path

    sessions = async_sessionmaker(api_db.engine, expire_on_commit=True)
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "test-secret-key-for-jwt-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as session:
        admin = await get_backup_key_admin(request, session)
        await put_backup_key(BackupKeyRequest(key="old"), request, session, admin)
        key_path().unlink()
        admin = await get_backup_key_admin(request, session)
        result = await recover_backup_key(data=BackupKeyRequest(key="old"), request=request, db=session, current_user=admin, audit_service=AuditService())
        assert result == {"configured": True}


@pytest.mark.asyncio
async def test_key_endpoint_commit_failure_does_not_remove_existing_key(auth_client, db_session, monkeypatch):
    import app.api.settings as api
    from app.services.backup_crypto import key_path

    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "old"}).status_code == 200
    async def fail(*args):
        raise RuntimeError("DB write failed")
    monkeypatch.setattr(api, "persist_required", fail)
    assert auth_client.delete("/api/v1/settings/backup-key").status_code == 500
    assert key_path().read_text() == "old"


@pytest.mark.asyncio
async def test_key_status_reports_unsafe_when_adoption_fails_without_losing_intent(auth_client, db_session):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import key_path

    key_path().write_text("unsafe")
    key_path().chmod(0o644)
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 503
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required


@pytest.mark.asyncio
async def test_key_set_unsafe_file_adoption_remains_fail_closed_after_file_removed(auth_client, db_session):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import intent_path, key_path

    key_path().write_text("old")
    key_path().chmod(0o644)
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "new"}).status_code == 503
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required
    key_path().unlink()
    intent_path().unlink()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


@pytest.mark.asyncio
async def test_key_recovery_unsafe_file_adoption_remains_fail_closed_after_file_removed(auth_client, db_session):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import intent_path, key_path

    key_path().write_text("old")
    key_path().chmod(0o644)
    assert auth_client.put("/api/v1/settings/backup-key/recover", json={"key": "new"}).status_code == 503
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required
    key_path().unlink()
    intent_path().unlink()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


@pytest.mark.asyncio
async def test_key_status_persists_intent_before_reporting_missing(auth_client, db_session):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import _set_intent

    _set_intent()
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True, "status": "missing"}
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("put", "/api/v1/settings/backup-key", {"key": "new"}),
    ("put", "/api/v1/settings/backup-key/recover", {"key": "new"}),
    ("delete", "/api/v1/settings/backup-key", None),
])
async def test_key_actions_revalidate_after_durable_intent_commit(auth_client, db_session, method, path, body, monkeypatch):
    import app.api.settings as api
    from app.services.backup_crypto import key_path

    if path.endswith("/recover"):
        assert auth_client.put("/api/v1/settings/backup-key", json={"key": "old"}).status_code == 200
        key_path().unlink()
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    original = api._authenticate_backup_admin
    calls = 0

    async def demote_before_second_auth(request, db):
        nonlocal calls
        calls += 1
        if calls == 3:
            admin.role = "standard"
            await db_session.commit()
        return await original(request, db)

    monkeypatch.setattr(api, "_authenticate_backup_admin", demote_before_second_auth)
    response = getattr(auth_client, method)(path, **({"json": body} if body is not None else {}))
    assert response.status_code == 403
    assert not key_path().exists()


@pytest.mark.asyncio
async def test_key_set_rechecks_backup_dir_after_durable_intent_commit(auth_client, db_session, tmp_path, monkeypatch):
    import app.api.settings as api
    from app.services.backup_crypto import key_path

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "outside")
    await db_session.commit()
    original = api._authenticate_backup_admin
    calls = 0
    async def change_dir_before_second_auth(request, db):
        nonlocal calls
        calls += 1
        if calls == 3:
            settings.backup_dir = str(key_path().parent)
            await db_session.commit()
        return await original(request, db)
    monkeypatch.setattr(api, "_authenticate_backup_admin", change_dir_before_second_auth)
    response = auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"})
    assert response.status_code == 400
    assert not key_path().exists()


@pytest.mark.asyncio
async def test_key_recovery_rechecks_backup_dir_after_durable_intent_commit(auth_client, db_session, tmp_path, monkeypatch):
    import app.api.settings as api
    from app.services.backup_crypto import key_path

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "outside")
    await db_session.commit()
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "old"}).status_code == 200
    key_path().unlink()
    original = api._authenticate_backup_admin
    calls = 0
    async def change_dir_before_second_auth(request, db):
        nonlocal calls
        calls += 1
        if calls == 3:
            settings.backup_dir = str(key_path().parent)
            await db_session.commit()
        return await original(request, db)
    monkeypatch.setattr(api, "_authenticate_backup_admin", change_dir_before_second_auth)
    response = auth_client.put("/api/v1/settings/backup-key/recover", json={"key": "new"})
    assert response.status_code == 400
    assert not key_path().exists()


@pytest.mark.asyncio
async def test_key_adoption_does_not_commit_settings_transaction(api_db, seeded_db, tmp_path):
    from app.core.security import lock_auth_settings
    from app.services.backup_crypto import database_configured_key, key_path

    key_path().write_text("existing")
    key_path().chmod(0o600)
    async with api_db.sessionmaker() as session:
        settings = await lock_auth_settings(session)
        settings.dns_primary = "9.9.9.9"
        await database_configured_key(session)
        await session.rollback()
    async with api_db.sessionmaker() as check:
        settings = (await check.execute(select(GlobalSettings))).scalar_one()
        assert settings.dns_primary != "9.9.9.9"


@pytest.mark.asyncio
async def test_key_lock_is_held_until_settings_update_commits(auth_client, db_session, tmp_path, monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager
    from app.services import backup_crypto
    import app.api.settings as api

    key_path = backup_crypto.key_path()
    key_path.write_text("old")
    key_path.chmod(0o600)
    original_lock = api.key_lock
    observed = []

    @asynccontextmanager
    async def tracked_lock():
        async with original_lock():
            try:
                yield
            finally:
                settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
                await db_session.refresh(settings)
                observed.append(settings.backup_dir)

    monkeypatch.setattr(api, "key_lock", tracked_lock)
    destination = str(tmp_path / "new-backups")
    response = await asyncio.to_thread(auth_client.put, GLOBAL_URL, json={"backup_dir": destination})
    assert response.status_code == 200
    assert observed == [destination]


@pytest.mark.asyncio
async def test_failed_key_adoption_does_not_commit_settings_changes(auth_client, db_session, tmp_path):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import key_path

    key_path().write_text("old")
    key_path().chmod(0o600)
    response = auth_client.put(GLOBAL_URL, json={"backup_dir": str(tmp_path / "new"), "dns_primary": "invalid"})
    assert response.status_code == 400
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_adoption_keeps_sqlite_settings_lock_until_transaction_end(tmp_path):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.core.database import Base
    from app.core.security import lock_auth_settings
    from app.services.backup_crypto import database_configured_key, key_path

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'adoption.db'}", connect_args={"timeout": 2})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        session.add(GlobalSettings(secret_key="secret", backup_dir="backups"))
        await session.commit()
    key_path().write_text("old")
    key_path().chmod(0o600)
    async with sessions() as first, sessions() as second:
        await lock_auth_settings(first)
        await database_configured_key(first)
        changed = asyncio.Event()
        async def change():
            await second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1"))
            await second.commit()
            changed.set()
        task = asyncio.create_task(change())
        try:
            await asyncio.sleep(0.15)
            assert not changed.is_set()
            await first.rollback()
            await asyncio.wait_for(task, 3)
        finally:
            await first.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_lock_release_after_failed_status_does_not_leave_sqlite_write_lock(tmp_path):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    from app.api.settings import get_backup_key
    from app.core.database import Base
    from app.services.backup_crypto import _set_intent, key_path

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'failed-status.db'}", connect_args={"timeout": 0.3})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir="backups", setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    _set_intent()
    key_path().write_text("unsafe")
    key_path().chmod(0o644)
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as first, sessions() as second:
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            await get_backup_key(request, first, None)
        await asyncio.wait_for(second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1")), 2)
        await second.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_lock_release_after_failed_key_operation_rolls_back_sqlite_auth_lock(tmp_path):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    from fastapi import HTTPException
    from app.api.settings import BackupKeyRequest, put_backup_key
    from app.core.database import Base
    from app.services.backup_crypto import _set_intent

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'failed-key.db'}", connect_args={"timeout": 0.3})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    _set_intent()
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as first, sessions() as second:
        with pytest.raises(HTTPException):
            await put_backup_key(BackupKeyRequest(key="new"), request, first, None)
        await asyncio.wait_for(second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1")), 2)
        await second.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_lock_release_after_failed_recovery_does_not_hold_sqlite_write_lock(tmp_path):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    from fastapi import HTTPException
    from app.api.settings import BackupKeyRequest, recover_backup_key
    from app.core.database import Base
    from app.services.audit_logger import AuditService

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'failed-recover.db'}", connect_args={"timeout": 0.3})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as first, sessions() as second:
        with pytest.raises(HTTPException):
            await recover_backup_key(data=BackupKeyRequest(key="new"), request=request, db=first, current_user=None, audit_service=AuditService())
        await asyncio.wait_for(second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1")), 2)
        await second.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_lock_release_after_failed_global_update_does_not_hold_sqlite_write_lock(tmp_path):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    from fastapi import HTTPException
    from app.api.settings import update_global_settings
    from app.core.database import Base
    from app.schemas.settings import GlobalSettingsUpdate
    from app.services.audit_logger import AuditService

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'failed-global.db'}", connect_args={"timeout": 0.3})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as first, sessions() as second:
        with pytest.raises(HTTPException):
            await update_global_settings(settings_data=GlobalSettingsUpdate(backup_dir=str(tmp_path / "new"), dns_primary="invalid"), request=request, db=first, current_user=None, audit_service=AuditService())
        await asyncio.wait_for(second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1")), 2)
        await second.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_lock_release_after_failed_setup_update_rolls_back_sqlite_lock(tmp_path):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    from fastapi import HTTPException
    from app.api.setup import configure_global_settings
    from app.core.database import Base
    from app.schemas.setup import ConfigureGlobals
    from app.services.backup_crypto import set_key, key_path

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'failed-setup.db'}", connect_args={"timeout": 0.3})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=False))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    set_key("secret")
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as first, sessions() as second:
        with pytest.raises(HTTPException):
            await configure_global_settings(ConfigureGlobals(secret_key="a" * 40, backup_dir=str(key_path().parent)), request, first)
        await asyncio.wait_for(second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1")), 2)
        await second.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_lock_release_after_failed_backup_does_not_hold_sqlite_write_lock(tmp_path, monkeypatch):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.core.database import Base
    from app.services.backup_crypto import set_key
    from app.services.backup_service import BackupService
    import app.services.backup_service as module

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'failed-backup.db'}", connect_args={"timeout": 0.3})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="secret", backup_dir=str(tmp_path / "backups"), setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    set_key("secret")
    monkeypatch.setattr(module, "encrypt_backup", lambda *args: (_ for _ in ()).throw(RuntimeError("failure")))
    async with sessions() as first, sessions() as second:
        with pytest.raises(RuntimeError):
            await BackupService().create_backup(first, user_id=1)
        await asyncio.wait_for(second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1")), 2)
        await second.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_lock_release_after_successful_global_update_releases_audit_write_lock(tmp_path):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    from app.api.settings import update_global_settings
    from app.core.database import Base
    from app.schemas.settings import GlobalSettingsUpdate
    from app.services.audit_logger import AuditService

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'success-global.db'}", connect_args={"timeout": 0.3})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as first, sessions() as second:
        await update_global_settings(settings_data=GlobalSettingsUpdate(backup_dir=str(tmp_path / "new")), request=request, db=first, current_user=None, audit_service=AuditService())
        await asyncio.wait_for(second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1")), 2)
        await second.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_lock_release_after_successful_setup_update_releases_database_lock(tmp_path):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    from app.api.setup import configure_global_settings
    from app.core.database import Base
    from app.schemas.setup import ConfigureGlobals

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'success-setup.db'}", connect_args={"timeout": 0.3})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=False))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    async with sessions() as first, sessions() as second:
        await configure_global_settings(ConfigureGlobals(secret_key="a" * 40, backup_dir=str(tmp_path / "new")), request, first)
        await asyncio.wait_for(second.execute(update(GlobalSettings).values(dns_primary="1.1.1.1")), 2)
        await second.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_settings_update_preserves_auth_lock_after_key_adoption(tmp_path, monkeypatch):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    import app.api.settings as api
    from app.core.database import Base
    from app.schemas.settings import GlobalSettingsUpdate
    from app.services.audit_logger import AuditService
    from app.services.backup_crypto import key_path

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'settings-race.db'}", connect_args={"timeout": 2})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    key_path().write_text("old")
    key_path().chmod(0o600)
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    adopted, proceed = asyncio.Event(), asyncio.Event()
    original = api.database_configured_key
    async def pause(db):
        value = await original(db)
        adopted.set()
        await proceed.wait()
        return value
    monkeypatch.setattr(api, "database_configured_key", pause)
    async with sessions() as writer, sessions() as demoter:
        op = asyncio.create_task(api.update_global_settings(settings_data=GlobalSettingsUpdate(backup_dir=str(tmp_path / "new")), request=request, db=writer, current_user=None, audit_service=AuditService()))
        await asyncio.wait_for(adopted.wait(), 2)
        demoted = asyncio.Event()
        async def change():
            await demoter.execute(update(User).where(User.id == 1).values(role="standard"))
            await demoter.commit()
            demoted.set()
        other = asyncio.create_task(change())
        try:
            await asyncio.sleep(0.15)
            assert not demoted.is_set()
            proceed.set()
            await asyncio.wait_for(op, 3)
            await writer.commit()
            await asyncio.wait_for(other, 3)
        finally:
            proceed.set()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_location_update_does_not_commit_settings_on_invalid_destination(auth_client, db_session, tmp_path):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import key_path

    key_path().write_text("old")
    key_path().chmod(0o600)
    response = auth_client.put(GLOBAL_URL, json={"backup_dir": str(key_path().parent)})
    assert response.status_code == 400
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one_or_none() is None
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    assert settings.backup_dir != str(key_path().parent)


@pytest.mark.asyncio
async def test_key_set_holds_sqlite_auth_lock_during_file_write(tmp_path, monkeypatch):
    import asyncio
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from app.core.database import Base
    from app.api.settings import BackupKeyRequest, put_backup_key
    import app.api.settings as api
    from jose import jwt

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth-lock.db'}", connect_args={"timeout": 2})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    file_stage = asyncio.Event()
    allow_file = asyncio.Event()

    # Pause the second locked authentication immediately before the filesystem write.
    original_auth = api._authenticate_backup_admin
    count = 0
    async def pause_auth(*args):
        nonlocal count
        user = await original_auth(*args)
        count += 1
        if count == 2:
            file_stage.set()
            await allow_file.wait()
        return user
    monkeypatch.setattr(api, "_authenticate_backup_admin", pause_auth)
    async with sessions() as writer, sessions() as demoter:
        operation = asyncio.create_task(put_backup_key(BackupKeyRequest(key="secret"), request, writer, None))
        await asyncio.wait_for(file_stage.wait(), 2)
        demoted = asyncio.Event()
        async def change():
            await demoter.execute(update(User).where(User.id == 1).values(role="standard"))
            await demoter.commit()
            demoted.set()
        task = asyncio.create_task(change())
        try:
            await asyncio.sleep(0.15)
            assert not demoted.is_set()
            allow_file.set()
            assert (await asyncio.wait_for(operation, 3))["configured"] is True
            await asyncio.wait_for(task, 3)
        finally:
            allow_file.set()
    await engine.dispose()


@pytest.mark.asyncio
async def test_key_set_persists_intent_before_file_failure_in_separate_connection(tmp_path, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from starlette.requests import Request
    from jose import jwt
    import app.api.settings as api
    from app.core.database import Base
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import key_path

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'intent.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="key-for-signing", backup_dir=str(tmp_path / "backups"), setup_completed=True))
        seed.add(User(id=1, username="admin", email="admin@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    token = jwt.encode({"sub": "admin", "exp": 9999999999}, "key-for-signing", algorithm="HS256")
    request = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    monkeypatch.setattr(api, "set_key", lambda *args: (_ for _ in ()).throw(RuntimeError("disk failure")))
    async with sessions() as writer:
        with pytest.raises(RuntimeError, match="disk failure"):
            await api.put_backup_key(api.BackupKeyRequest(key="secret"), request, writer, None)
        await writer.rollback()
    async with sessions() as check:
        assert (await check.execute(select(BackupEncryptionState))).scalar_one().required
    assert not key_path().exists()
    await engine.dispose()


@pytest.mark.asyncio
async def test_existing_backup_dir_can_contain_default_key_path_when_no_key_configured(auth_client, db_session, tmp_path):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path)
    await db_session.commit()
    response = auth_client.post("/api/v1/backups/", json={})
    assert response.status_code == 201
    assert response.json()["is_encrypted"] is False
    assert auth_client.put(GLOBAL_URL, json={"backup_dir": str(tmp_path)}).status_code == 200


@pytest.mark.asyncio
async def test_key_rotation_checks_backup_dir_inside_shared_lock(auth_client, db_session, tmp_path, monkeypatch):
    import asyncio
    from app.core.config_loader import config_loader
    from app.services.backup_crypto import key_lock

    from threading import Event, Thread

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "outside")
    await db_session.commit()
    started = Event()
    outcome = []

    def set_key():
        started.set()
        outcome.append(auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}))

    async with key_lock():
        worker = Thread(target=set_key)
        worker.start()
        assert await asyncio.to_thread(started.wait, 2)
        await asyncio.sleep(0.1)
        settings.backup_dir = str(config_loader.config_path.parent)
        await db_session.commit()
    await asyncio.to_thread(worker.join, 5)
    assert not worker.is_alive()
    assert outcome[0].status_code == 400


@pytest.mark.asyncio
async def test_key_recovery_checks_backup_dir_inside_shared_lock(auth_client, db_session, tmp_path):
    import asyncio
    from threading import Event, Thread
    from app.core.config_loader import config_loader
    from app.services.backup_crypto import key_lock, key_path

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "outside")
    await db_session.commit()
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200
    key_path().unlink()
    started = Event()
    outcome = []

    def recover():
        started.set()
        outcome.append(auth_client.put("/api/v1/settings/backup-key/recover", json={"key": "secret"}))

    async with key_lock():
        worker = Thread(target=recover)
        worker.start()
        assert await asyncio.to_thread(started.wait, 2)
        await asyncio.sleep(0.1)
        settings.backup_dir = str(config_loader.config_path.parent)
        await db_session.commit()
    await asyncio.to_thread(worker.join, 5)
    assert not worker.is_alive()
    assert outcome[0].status_code == 400
    assert not key_path().exists()


@pytest.mark.asyncio
async def test_settings_write_does_not_commit_before_validation(auth_client, db_session, tmp_path):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = True
    await db_session.commit()
    response = auth_client.put(GLOBAL_URL, json={"backup_dir": str(tmp_path / "backups"), "disable_auth": True, "dns_primary": "invalid"})
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert not settings.disable_auth


@pytest.mark.asyncio
async def test_no_key_backup_works_with_read_only_config_directory(auth_client, db_session, tmp_path, monkeypatch):
    import os
    from app.core.config_loader import config_loader
    from app.services import backup_crypto

    config = config_loader.config_path
    config.write_text('{"database":{"type":"sqlite","url":"sqlite://"}}')
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "backups")
    await db_session.commit()
    original_open = os.open

    def deny_config_writes(path, flags, *args, **kwargs):
        if str(path).startswith(str(config.parent / ".backup-key")) and flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
            raise PermissionError("read-only config")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(backup_crypto.os, "open", deny_config_writes)
    response = auth_client.post("/api/v1/backups/", json={})
    assert response.status_code == 201
    assert response.json()["is_encrypted"] is False


@pytest.mark.asyncio
async def test_plaintext_backup_works_when_external_key_directory_does_not_exist(auth_client, db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(tmp_path / "not-present" / "nested" / "backup.key"))
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "backups")
    await db_session.commit()
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False
    assert not (tmp_path / "not-present").exists()


@pytest.mark.asyncio
async def test_external_key_works_with_read_only_config_directory(auth_client, db_session, tmp_path, monkeypatch):
    import os
    from app.core.config_loader import config_loader
    from app.services import backup_crypto

    config = config_loader.config_path
    config.write_text('{"database":{"type":"sqlite","url":"sqlite://"}}')
    key_dir = tmp_path / "external-key"
    key_dir.mkdir()
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(key_dir / "backup.key"))
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "backups")
    await db_session.commit()
    original_open = os.open

    def deny_config_writes(path, flags, *args, **kwargs):
        path = str(path)
        if path == str(config.parent / ".backup-key-lock") or path == str(config.parent / ".backup-key-required") or path.startswith(str(config.parent / ".backup-key-intent-")):
            if flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
                raise PermissionError("read-only config")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(backup_crypto.os, "open", deny_config_writes)
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True
    assert auth_client.put(GLOBAL_URL, json={"backup_dir": str(tmp_path / "other-backups")}).status_code == 200


@pytest.mark.asyncio
async def test_external_key_does_not_require_backup_dir_to_avoid_readonly_config_directory(auth_client, db_session, tmp_path, monkeypatch):
    from app.core.config_loader import config_loader

    external = tmp_path / "external" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(external))
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(config_loader, "config_path", config_dir / "config.json")
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(config_loader.config_path.parent)
    await db_session.commit()
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200


@pytest.mark.asyncio
async def test_key_lock_order_keeps_plaintext_backup_with_unwritable_config_parent(auth_client, db_session, tmp_path, monkeypatch):
    import os
    from app.core.config_loader import config_loader
    from app.services import backup_crypto

    config_dir = config_loader.config_path.parent
    key_path = tmp_path / "external" / "nested" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(key_path))
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "backups")
    await db_session.commit()
    original = os.open
    def deny_config_create(path, flags, *args, **kwargs):
        if str(path).startswith(str(config_dir / ".backup-key")) and flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
            raise PermissionError("read-only config")
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(backup_crypto.os, "open", deny_config_create)
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False
    assert not key_path.parent.exists()


@pytest.mark.asyncio
async def test_key_lock_fails_closed_when_config_directory_is_not_lockable(auth_client, db_session, tmp_path, monkeypatch):
    import os
    from app.core.config_loader import config_loader
    from app.services import backup_crypto

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path / "backups")
    await db_session.commit()
    original = os.open
    def deny_config(path, flags, *args, **kwargs):
        if str(path) == str(config_loader.config_path.parent):
            raise PermissionError("cannot lock directory")
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(backup_crypto.os, "open", deny_config)
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert not (tmp_path / "backups").exists()


@pytest.mark.asyncio
async def test_external_key_locks_share_identity_across_different_config_paths(tmp_path, monkeypatch):
    import asyncio
    from app.core.config_loader import config_loader
    from app.services.backup_crypto import key_lock

    key_dir = tmp_path / "key"
    key_dir.mkdir()
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(key_dir / "backup.key"))
    monkeypatch.setattr(config_loader, "config_path", first / "config.json")
    async with key_lock():
        monkeypatch.setattr(config_loader, "config_path", second / "config.json")
        acquired = asyncio.Event()
        async def competitor():
            async with key_lock():
                acquired.set()
        task = asyncio.create_task(competitor())
        try:
            await asyncio.sleep(0.1)
            assert not acquired.is_set()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_key_lock_serializes_key_paths_when_config_and_key_directories_are_swapped(tmp_path, monkeypatch):
    import asyncio
    from app.core.config_loader import config_loader
    from app.services.backup_crypto import key_lock

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setattr(config_loader, "config_path", first / "config.json")
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(second / "backup.key"))
    async with key_lock():
        monkeypatch.setattr(config_loader, "config_path", second / "config.json")
        monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(first / "backup.key"))
        acquired = asyncio.Event()
        async def competitor():
            async with key_lock():
                acquired.set()
        task = asyncio.create_task(competitor())
        try:
            await asyncio.sleep(0.1)
            assert not acquired.is_set()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_key_and_backup_settings_lock_order_does_not_deadlock(api_db, seeded_db, tmp_path):
    import asyncio
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.core.database import Base
    from app.core.security import lock_auth_settings
    from app.models.settings import GlobalSettings
    from app.services.backup_crypto import database_configured_key, key_lock

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lock-test.db'}", connect_args={"timeout": 0.5})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as setup:
        setup.add(GlobalSettings(secret_key="secret", backup_dir="backups"))
        await setup.commit()
    async with sessions() as settings_session, sessions() as backup_session:
        backup_holds_key = asyncio.Event()
        release_backup = asyncio.Event()
        settings_holds_db = asyncio.Event()

        async def backup():
            async with key_lock():
                backup_holds_key.set()
                await release_backup.wait()
                await database_configured_key(backup_session)
                await backup_session.commit()

        async def change_settings():
            async with key_lock():
                await lock_auth_settings(settings_session)
                await database_configured_key(settings_session)
                settings_holds_db.set()

        task = asyncio.create_task(backup())
        await asyncio.wait_for(backup_holds_key.wait(), 2)
        settings_task = asyncio.create_task(change_settings())
        await asyncio.sleep(0.1)
        assert not settings_holds_db.is_set()
        release_backup.set()
        try:
            await asyncio.wait_for(asyncio.gather(task, settings_task), 2)
        finally:
            await settings_session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_external_key_directory_creation_does_not_change_lock_domain(auth_client, db_session, tmp_path, monkeypatch):
    import asyncio
    from app.services.backup_crypto import key_lock, key_path

    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(tmp_path / "new" / "nested" / "backup.key"))
    acquired = asyncio.Event()
    async with key_lock():
        key_path().parent.mkdir(parents=True)
        async def competitor():
            async with key_lock():
                acquired.set()
        task = asyncio.create_task(competitor())
        try:
            await asyncio.sleep(0.15)
            assert not acquired.is_set()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_nested_config_directory_alias_does_not_create_new_lock_domain(tmp_path, monkeypatch):
    import asyncio
    from app.core.config_loader import config_loader
    from app.services.backup_crypto import key_lock

    parent = tmp_path / "parent"
    parent.mkdir()
    monkeypatch.setattr(config_loader, "config_path", parent / "config.json")
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(parent / "nested" / "backup.key"))
    acquired = asyncio.Event()
    async with key_lock():
        (parent / "nested").mkdir()
        async def competitor():
            async with key_lock():
                acquired.set()
        task = asyncio.create_task(competitor())
        try:
            await asyncio.sleep(0.1)
            assert not acquired.is_set()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_key_lock_does_not_require_write_permission_in_external_parent(tmp_path, monkeypatch):
    import os
    from app.services import backup_crypto

    parent = tmp_path / "key-dir"
    parent.mkdir()
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(parent / "backup.key"))
    original_open = os.open

    def deny_writes(path, flags, *args, **kwargs):
        if str(path).startswith(str(parent)) and flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
            raise PermissionError("read-only directory")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(backup_crypto.os, "open", deny_writes)
    async with backup_crypto.key_lock():
        pass
    assert not (parent / ".backup-key-lock").exists()


@pytest.mark.asyncio
async def test_anonymous_settings_cannot_leak_signing_or_oidc_secrets(api_client, seeded_db, db_session):
    from jose import jwt

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    settings.oidc_client_secret = "private-oidc-secret"
    settings.database_url = "postgresql+asyncpg://user:database-password@db/linguard?password=query-password&token=query-token&sslmode=require"
    await db_session.commit()
    response = api_client.get(GLOBAL_URL)
    assert response.status_code == 200
    assert settings.secret_key not in response.text
    assert settings.oidc_client_secret not in response.text
    assert "database-password" not in response.text
    assert "query-password" not in response.text
    assert "query-token" not in response.text
    assert "require" not in response.json()["database_url"]
    assert "db/linguard" in response.json()["database_url"]
    assert response.json()["backup_dir"]
    oidc_response = api_client.get("/api/v1/auth/oidc/config")
    assert settings.secret_key not in oidc_response.text
    assert settings.oidc_client_secret not in oidc_response.text
    stolen = response.json().get("secret_key")
    assert not stolen
    forged = jwt.encode({"sub": "admin", "exp": 9999999999}, stolen or "wrong", algorithm=settings.algorithm)
    headers = {"Authorization": f"Bearer {forged}"}
    assert api_client.get("/api/v1/settings/backup-key", headers=headers).status_code == 401
    assert api_client.post("/api/v1/backups/", headers=headers, json={}).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("database_url", [
    "postgresql+asyncpg://user:pw@db/name?password=secret&password=other&socket=/private/path",
    "sqlite+aiosqlite:///data.db?uri=true&token=secret",
    "not-a-url?token=secret",
])
async def test_settings_never_exposes_database_query_values(api_client, seeded_db, db_session, database_url):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    settings.database_url = database_url
    await db_session.commit()
    response = api_client.get(GLOBAL_URL)
    assert response.status_code == 200
    for value in ("secret", "other", "/private/path"):
        assert value not in str(response.json().get("database_url"))


@pytest.mark.asyncio
async def test_setting_secret_changes_are_not_exposed_in_responses_or_audit(auth_client, db_session):
    value = "new-private-oidc-secret"
    response = auth_client.put(GLOBAL_URL, json={"oidc_client_secret": value})
    assert response.status_code == 200
    assert value not in response.text
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert value not in str([row.__dict__ for row in rows])


@pytest.mark.asyncio
async def test_settings_display_reports_oidc_secret_configured_without_value(auth_client, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.oidc_client_secret = "secret"
    await db_session.commit()
    body = auth_client.get(GLOBAL_URL).json()
    assert body["oidc_client_secret_configured"] is True
    assert "oidc_client_secret" not in body


@pytest.mark.asyncio
async def test_old_secret_audit_rows_are_not_available_anonymously(api_client, seeded_db, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    db_session.add(AuditLog(user_id=seeded_db["admin_id"], action="UPDATE", resource_type="settings", details={"new": {"secret_key": settings.secret_key}}))
    await db_session.commit()
    response = api_client.get("/api/v1/audit/")
    assert settings.secret_key not in response.text


@pytest.mark.asyncio
async def test_old_oidc_audit_fields_are_redacted_in_all_audit_routes(api_client, seeded_db, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    audit = AuditLog(user_id=seeded_db["admin_id"], action="UPDATE", resource_type="settings", resource_id=9,
                     details={"changes": [{"oidc_client_secret": "old-oidc-secret"}]})
    db_session.add(audit)
    await db_session.commit()
    for path in ("/api/v1/audit/", f"/api/v1/audit/{audit.id}", "/api/v1/audit/resource/settings/9", f"/api/v1/audit/user/{seeded_db['admin_id']}/actions"):
        response = api_client.get(path)
        assert response.status_code == 200
        assert "old-oidc-secret" not in response.text


@pytest.mark.asyncio
async def test_old_settings_audit_does_not_expose_database_credentials(api_client, seeded_db, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    db_session.add(AuditLog(user_id=seeded_db["admin_id"], action="UPDATE", resource_type="settings",
                            details={"new": {"database_url": "postgresql://user:db-secret@host/db"}}))
    await db_session.commit()
    assert "db-secret" not in api_client.get("/api/v1/audit/").text


@pytest.mark.asyncio
async def test_anonymous_cannot_change_signing_key_with_auth_disabled(api_client, seeded_db, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    assert api_client.put(GLOBAL_URL, json={"secret_key": "attacker"}).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["key", "role"])
async def test_should_revalidate_admin_after_acquiring_settings_lock(api_db, db_session, seeded_db, change):
    from fastapi import HTTPException
    from jose import jwt
    from starlette.requests import Request
    from app.api.settings import update_global_settings
    from app.schemas.settings import GlobalSettingsUpdate
    from app.services.audit_logger import AuditService

    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    token = jwt.encode({"sub": "admin", "auth_method": "local", "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    async with api_db.sessionmaker() as session:
        stale_admin = (await session.execute(select(User).where(User.id == admin.id))).scalar_one()
        await session.execute(select(GlobalSettings))
        if change == "key":
            settings.secret_key = "new-key"
        else:
            admin.role = "standard"
        await db_session.commit()
        request = Request({"type": "http", "method": "PUT", "path": GLOBAL_URL,
                           "headers": [(b"authorization", f"Bearer {token}".encode())]})
        with pytest.raises(HTTPException) as exc:
            await update_global_settings(settings_data=GlobalSettingsUpdate(dns_primary="1.1.1.1"), request=request, db=session, current_user=stale_admin, audit_service=AuditService())
        assert exc.value.status_code in (401, 403)


@pytest.mark.asyncio
async def test_should_reject_oidc_only_without_oidc_admin_session(auth_client, db_session):
    response = auth_client.put(GLOBAL_URL, json={"auth_mode": "oidc_only"})
    assert response.status_code == 400
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.auth_mode == "both"


@pytest.mark.asyncio
async def test_should_roll_back_revocation_when_settings_commit_fails(auth_client, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    response = auth_client.put(GLOBAL_URL, json={"oidc_admin_groups": "admins", "backup_dir": None})
    assert response.status_code == 500
    await db_session.refresh(settings)
    assert settings.setup_current_step is None
    assert settings.oidc_admin_groups == ""
    assert auth_client.get("/api/v1/auth/profile").status_code == 200


@pytest.mark.asyncio
async def test_should_reject_oidc_only_through_settings_during_setup(auth_client, db_session):
    from jose import jwt

    from app.api.settings import oidc_configuration_fingerprint

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    settings.oidc_discovery_url = "https://idp.example.com/discovery"
    settings.oidc_client_id = "client"
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    admin.oidc_sub = "sso-admin"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "exp": 9999999999, "oidc_config": oidc_configuration_fingerprint(settings)}, settings.secret_key, algorithm=settings.algorithm)
    response = auth_client.put(GLOBAL_URL, headers={"Authorization": f"Bearer {token}"}, json={"auth_mode": "oidc_only"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_should_reject_provider_changes_in_oidc_only(auth_client, db_session):
    from jose import jwt
    from app.core.security import oidc_configuration_fingerprint

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.auth_mode = "oidc_only"
    settings.oidc_discovery_url = "https://idp.example.com/discovery"
    settings.oidc_client_id = "client"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "auth_method": "oidc", "oidc_config": oidc_configuration_fingerprint(settings), "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    response = auth_client.put(GLOBAL_URL, headers={"Authorization": f"Bearer {token}"}, json={"oidc_client_id": "different"})
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert settings.oidc_client_id == "client"


@pytest.mark.asyncio
async def test_should_not_reinterpret_existing_oidc_subjects_under_another_provider(auth_client, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.oidc_discovery_url = "https://idp.example.com/discovery"
    settings.oidc_client_id = "client"
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    admin.oidc_sub = "existing-sub"
    await db_session.commit()
    response = auth_client.put(GLOBAL_URL, json={"oidc_discovery_url": "https://other.example.com/discovery"})
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert settings.oidc_discovery_url == "https://idp.example.com/discovery"


def _headers(username, secret="test-secret-key-for-jwt-signing"):
    from datetime import datetime, timedelta

    from jose import jwt

    token = jwt.encode(
        {"sub": username, "exp": datetime.utcnow() + timedelta(minutes=30)},
        secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_should_return_global_settings_when_admin_requests_them(auth_client, isolated_config):
    response = auth_client.get(GLOBAL_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["database_type"] == "sqlite"
    assert body["database_url"].startswith("sqlite+aiosqlite:///")
    assert body["auth_mode"] == "both"
    assert body["setup_completed"] is True
    assert body["created_at"].endswith("Z")


@pytest.mark.asyncio
async def test_should_keep_existing_database_url_when_already_set(auth_client, db_session, isolated_config):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.database_url = "postgresql+asyncpg://db/linguard"
    settings.database_type = "postgresql"
    await db_session.commit()

    response = auth_client.get(GLOBAL_URL)

    assert response.status_code == 200
    assert response.json()["database_url"] == "postgresql+asyncpg://db/linguard"
    assert response.json()["database_type"] == "postgresql"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "expected_type"),
    [
        ("postgresql+asyncpg://user:pass@db:5432/linguard", "postgresql"),
        ("mysql+aiomysql://user:pass@db/linguard", "mysql"),
        ("oracle+cx_oracle://user:pass@db:1521/xe", "unknown"),
    ],
)
async def test_should_detect_database_type_from_config_url_when_unset(
    auth_client, db_session, isolated_config, url, expected_type
):
    isolated_config.write_text(f'{{"database": {{"type": "x", "url": "{url}"}}}}')

    response = auth_client.get(GLOBAL_URL)

    assert response.status_code == 200
    assert response.json()["database_url"] == url.replace(":pass@", ":***@")
    assert response.json()["database_type"] == expected_type


@pytest.mark.asyncio
async def test_should_create_default_settings_row_when_none_exists_on_read(api_db, db_session, isolated_config):
    """Defensive path: the router can bootstrap settings when the row is missing.

    Unreachable through HTTP (authentication itself needs the settings row), so
    the handler is called directly against the real test database.
    """
    from app.api.settings import get_global_settings

    async with api_db.sessionmaker() as session:
        settings = await get_global_settings(db=session, current_user=None)

    assert settings.metrics_collection_interval_minutes == 5
    assert settings.metrics_retention_days == 90
    assert settings.metrics_global_notifications_per_hour == 50
    assert settings.database_type == "sqlite"

    rows = (await db_session.execute(select(GlobalSettings))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_should_create_default_settings_row_when_none_exists_on_update(api_db, db_session, isolated_config):
    """Defensive path: an update bootstraps the settings row before applying."""
    from starlette.requests import Request

    from app.api.settings import update_global_settings
    from app.schemas.settings import GlobalSettingsUpdate
    from app.services.audit_logger import AuditService

    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password="x",
        role="admin",
        auth_provider="local",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    request = Request({"type": "http", "method": "PUT", "path": GLOBAL_URL, "headers": []})

    async with api_db.sessionmaker() as session:
        settings = await update_global_settings(
            settings_data=GlobalSettingsUpdate(dns_primary="1.0.0.1"),
            request=request,
            db=session,
            current_user=admin,
            audit_service=AuditService(),
        )

    assert settings.dns_primary == "1.0.0.1"
    rows = (await db_session.execute(select(GlobalSettings))).scalars().all()
    assert len(rows) == 1
    assert rows[0].dns_primary == "1.0.0.1"


@pytest.mark.asyncio
async def test_should_reject_global_settings_when_not_authenticated(api_client, seeded_db):
    response = api_client.get(GLOBAL_URL)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_should_return_503_when_setup_not_completed_and_settings_requested(api_client):
    response = api_client.get(GLOBAL_URL, headers=_headers("admin"))

    assert response.status_code == 503
    assert response.json()["detail"] == "Application not configured. Please complete setup first."


@pytest.mark.asyncio
async def test_should_deny_global_settings_update_when_user_is_not_admin(user_client):
    response = user_client.put(GLOBAL_URL, json={"dns_primary": "1.1.1.1"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"


@pytest.mark.asyncio
async def test_should_update_dns_and_audit_when_admin_puts_settings(auth_client, db_session):
    response = auth_client.put(
        GLOBAL_URL,
        json={"dns_primary": "9.9.9.9", "dns_secondary": "149.112.112.112"},
    )

    assert response.status_code == 200
    assert response.json()["dns_primary"] == "9.9.9.9"
    assert response.json()["dns_secondary"] == "149.112.112.112"

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.dns_primary == "9.9.9.9"

    audits = (await db_session.execute(select(AuditLog))).scalars().all()
    assert [a.action for a in audits] == ["UPDATE"]
    assert audits[0].resource_name == "Global Settings"
    assert audits[0].details["new"] == {
        "dns_primary": "9.9.9.9",
        "dns_secondary": "149.112.112.112",
    }


@pytest.mark.asyncio
async def test_should_reject_invalid_primary_dns_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"dns_primary": "not-an-ip"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid primary DNS address: not-an-ip"


@pytest.mark.asyncio
async def test_should_reject_invalid_secondary_dns_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"dns_secondary": "999.1.1.1"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid secondary DNS address: 999.1.1.1"


@pytest.mark.asyncio
async def test_should_reject_blank_log_path_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"log_path": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Log file path cannot be empty. Please provide a valid file path."
    )


@pytest.mark.asyncio
async def test_should_reject_unknown_backup_frequency_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"backup_schedule_frequency": "hourly"})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Backup schedule frequency must be 'daily', 'weekly', or 'monthly'."
    )


@pytest.mark.asyncio
async def test_should_reject_out_of_range_backup_hour_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"backup_schedule_hour": 24})

    assert response.status_code == 400
    assert response.json()["detail"] == "Backup schedule hour must be between 0 and 23."


@pytest.mark.asyncio
async def test_should_reject_out_of_range_backup_minute_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"backup_schedule_minute": 60})

    assert response.status_code == 400
    assert response.json()["detail"] == "Backup schedule minute must be between 0 and 59."


@pytest.mark.asyncio
async def test_should_accept_null_backup_time_when_periodic_backups_disabled(auth_client, db_session):
    response = auth_client.put(
        GLOBAL_URL,
        json={
            "backup_periodic_enabled": False,
            "backup_schedule_hour": None,
            "backup_schedule_minute": None,
        },
    )

    assert response.status_code == 200
    assert response.json()["backup_periodic_enabled"] is False
    # The schedule columns are NOT NULL: a null value keeps the stored schedule.
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.backup_schedule_hour == 2
    assert settings.backup_schedule_minute == 0


@pytest.mark.asyncio
async def test_should_reject_unknown_auth_mode_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"auth_mode": "saml"})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Authentication mode must be 'both', 'local_only', or 'oidc_only'."
    )


@pytest.mark.asyncio
async def test_should_reject_non_http_oidc_url_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"oidc_discovery_url": "idp.example.com/discovery"})

    assert response.status_code == 400
    assert response.json()["detail"] == "OIDC discovery URL must start with http:// or https://."


@pytest.mark.asyncio
async def test_should_reconfigure_logging_when_log_path_changes(auth_client, tmp_path):
    new_log = tmp_path / "logs" / "linguard.log"

    with patch("app.main.configure_logging") as configure_logging:
        response = auth_client.put(GLOBAL_URL, json={"log_path": str(new_log)})

    assert response.status_code == 200
    configure_logging.assert_called_once_with(str(new_log))
