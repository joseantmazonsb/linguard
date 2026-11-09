import base64
import json
import stat

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.server import Server
from app.models.settings import GlobalSettings


@pytest.fixture(autouse=True)
def key_path(tmp_path, monkeypatch):
    from app.core.config_loader import config_loader

    path = tmp_path / "config" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(path))
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "config" / "linguard.config.json")
    path.parent.mkdir(parents=True)
    return path


async def test_key_settings_and_encrypted_download_import_restore(auth_client, backup_dir, key_path, seeded_server_and_peer):
    url = "/api/v1/settings/backup-key"
    assert auth_client.get(url).json() == {"configured": False}
    response = auth_client.put(url, json={"key": "original secret"})
    assert response.status_code == 200
    assert response.json() == {"configured": True}
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    created = auth_client.post("/api/v1/backups/", json={}).json()
    assert created["is_encrypted"] is True
    downloaded = auth_client.get(f"/api/v1/backups/{created['id']}/download").content
    assert b"original secret" not in downloaded
    assert b"peer-main" not in downloaded
    uploaded = auth_client.post("/api/v1/backups/upload", files={"file": ("backup.json", downloaded, "application/json")})
    assert uploaded.status_code == 201
    assert uploaded.json()["is_encrypted"] is True
    backup_id = uploaded.json()["id"]
    assert auth_client.post(f"/api/v1/backups/{backup_id}/restore", json={"overwrite": False}).status_code == 200
    assert auth_client.put(url, json={"key": "new secret"}).status_code == 200
    assert auth_client.post(f"/api/v1/backups/{backup_id}/restore", json={"overwrite": True}).status_code == 400
    assert auth_client.post(f"/api/v1/backups/{backup_id}/restore", json={"overwrite": False, "passphrase": "original secret"}).status_code == 200
    assert auth_client.delete(url).json() == {"configured": False}
    assert not key_path.exists()


async def test_tampering_and_kdf_abuse_rejected_before_clear(auth_client, backup_dir, db_session, seeded_server_and_peer):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"})
    created = auth_client.post("/api/v1/backups/", json={}).json()
    path = backup_dir / created["filename"]
    envelope = json.loads(path.read_text())
    for modified in ({**envelope, "ciphertext": "AA=="}, {**envelope, "n": 2**30}, {**envelope, "version": 99}):
        path.write_text(json.dumps(modified))
        response = auth_client.post(f"/api/v1/backups/{created['id']}/restore", json={"overwrite": True})
        assert response.status_code == 400
        assert (await db_session.execute(select(Server))).scalars().all()


async def test_missing_and_unreadable_key_fail_closed(auth_client, backup_dir, key_path):
    key_path.mkdir(parents=True)
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 503
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "new"}).status_code == 503
    assert auth_client.delete("/api/v1/settings/backup-key").status_code == 503
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert not backup_dir.exists() or not list(backup_dir.iterdir())


async def test_key_io_failures_are_reported_without_plaintext_fallback(auth_client, backup_dir, key_path, monkeypatch):
    import app.services.backup_crypto as crypto

    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "old"}).status_code == 200
    with monkeypatch.context() as patch:
        patch.setattr(crypto.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk error")))
        assert auth_client.put(url, json={"key": "new"}).status_code == 500
    assert key_path.read_text() == "old"
    with monkeypatch.context() as patch:
        patch.setattr(crypto.os, "unlink", lambda *args: (_ for _ in ()).throw(OSError("disk error")))
        assert auth_client.delete(url).status_code == 500
    assert key_path.read_text() == "old"
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True


async def test_failed_intent_directory_sync_keeps_encryption_required(auth_client, backup_dir, monkeypatch):
    import app.services.backup_crypto as crypto

    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "secret"}).status_code == 200
    original = crypto._sync_directory
    calls = 0

    def fail_second_sync(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("sync failed")
        return original(path)

    with monkeypatch.context() as patch:
        patch.setattr(crypto, "_sync_directory", fail_second_sync)
        assert auth_client.delete(url).status_code == 500
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_unsafe_key_permissions_fail_closed(auth_client, backup_dir, key_path):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "old"})
    key_path.chmod(0o644)
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 503
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "new"}).status_code == 503
    assert auth_client.delete("/api/v1/settings/backup-key").status_code == 503
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert key_path.read_text() == "old"


async def test_restore_rejects_passphrase_query(auth_client):
    response = auth_client.post("/api/v1/backups/1/restore?passphrase=secret")
    assert response.status_code == 400
    assert "secret" not in response.text


async def test_explicit_key_encrypts_without_global_key(auth_client, backup_dir):
    response = auth_client.post("/api/v1/backups/", json={"encrypt": True, "passphrase": "secret"})
    assert response.status_code == 201, response.text
    assert response.json()["is_encrypted"] is True
    backup_id = response.json()["id"]
    assert auth_client.post(f"/api/v1/backups/{backup_id}/restore", json={"passphrase": "secret", "overwrite": False}).status_code == 200


async def test_global_key_takes_precedence_and_uses_random_salt_and_nonce(auth_client, backup_dir):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "global"})
    first = auth_client.post("/api/v1/backups/", json={"encrypt": True, "passphrase": "other"}).json()
    second = auth_client.post("/api/v1/backups/", json={}).json()
    a = json.loads((backup_dir / first["filename"]).read_text())
    b = json.loads((backup_dir / second["filename"]).read_text())
    assert a["salt"] != b["salt"]
    assert a["nonce"] != b["nonce"]
    assert auth_client.post(f"/api/v1/backups/{first['id']}/restore", json={"passphrase": "other"}).status_code == 400
    assert auth_client.post(f"/api/v1/backups/{first['id']}/restore", json={}).status_code == 200


async def test_encrypted_upload_rejects_malformed_envelope(auth_client, backup_dir):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "global"})
    backup = auth_client.post("/api/v1/backups/", json={}).json()
    envelope = json.loads((backup_dir / backup["filename"]).read_text())
    envelope.pop("ciphertext")
    response = auth_client.post("/api/v1/backups/upload", files={"file": ("backup.json", json.dumps(envelope), "application/json")})
    assert response.status_code == 400


async def test_import_does_not_treat_damaged_envelope_as_plaintext(auth_client, backup_dir):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "global"})
    backup = auth_client.post("/api/v1/backups/", json={}).json()
    envelope = json.loads((backup_dir / backup["filename"]).read_text())
    envelope.pop("ciphertext")
    envelope.pop("format")
    response = auth_client.post("/api/v1/backups/upload", files={"file": ("backup.json", json.dumps(envelope), "application/json")})
    assert response.status_code == 400


async def test_import_rejects_stripped_envelope_with_numeric_version(auth_client, backup_dir):
    response = auth_client.post("/api/v1/backups/upload", files={"file": ("backup.json", '{"version": 1}', "application/json")})
    assert response.status_code == 400


async def test_key_endpoints_are_admin_only(user_client):
    url = "/api/v1/settings/backup-key"
    assert user_client.get(url).status_code == 403
    assert user_client.put(url, json={"key": "secret"}).status_code == 403
    assert user_client.delete(url).status_code == 403


async def test_key_endpoints_require_authentication_even_when_auth_is_disabled(api_client, seeded_db, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    assert api_client.get("/api/v1/settings/backup-key").status_code == 401
    assert api_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 401
    assert api_client.delete("/api/v1/settings/backup-key").status_code == 401


async def test_key_is_not_saved_in_audit_or_global_settings(auth_client, db_session, key_path):
    secret = "unique test key 382742"
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": secret}).status_code == 200
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True}
    response = auth_client.post("/api/v1/backups/", json={})
    assert secret not in response.text
    audits = (await db_session.execute(select(AuditLog))).scalars().all()
    assert secret not in str([row.__dict__ for row in audits])
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    assert secret not in str(settings.__dict__)
    assert key_path.read_text() == secret


async def test_empty_key_requires_explicit_delete(auth_client, key_path):
    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "original"}).status_code == 200
    assert auth_client.put(url, json={"key": ""}).status_code == 400
    assert key_path.read_text() == "original"


async def test_empty_key_on_unconfigured_server_does_not_enable_encryption(auth_client, backup_dir):
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": ""}).status_code == 400
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": False}
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_old_marker_is_persisted_even_if_key_already_missing(auth_client, db_session):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import _set_intent

    _set_intent()
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True, "status": "missing"}
    db_session.expire_all()
    state = (await db_session.execute(select(BackupEncryptionState))).scalar_one()
    assert state.required is True


async def test_import_persists_missing_key_adoption_before_releasing_lock(auth_client, db_session, backup_dir, monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.services.backup_service as module
    from app.core.database import Base, get_db
    from app.main import app
    from app.models.settings import BackupEncryptionState
    from app.models.user import User
    from app.services.backup_crypto import _set_intent

    _set_intent()
    engine = create_async_engine(f"sqlite+aiosqlite:///{backup_dir.parent / 'import-state.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    # Copy the seeded settings and admin into a file-backed database with separate connections.
    async with sessions() as seed:
        seed.add(GlobalSettings(secret_key="test-secret-key-for-jwt-signing", backup_dir=str(backup_dir), setup_completed=True))
        seed.add(User(id=1, username="admin", email="a@example.com", hashed_password="unused", role="admin"))
        await seed.commit()
    async def override():
        async with sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    app.dependency_overrides[get_db] = override
    original = module.key_lock
    observed = []

    @asynccontextmanager
    async def tracked_lock():
        async with original():
            try:
                yield
            finally:
                async with sessions() as check:
                    state = (await check.execute(select(BackupEncryptionState))).scalar_one_or_none()
                    observed.append(state.required if state else None)

    monkeypatch.setattr(module, "key_lock", tracked_lock)
    try:
        response = await asyncio.to_thread(auth_client.post, "/api/v1/backups/upload", files={"file": ("backup.json", b'{"version":"1.0"}')})
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()
    assert response.status_code == 201
    assert observed == [True]


async def test_old_marker_can_be_recovered_without_first_calling_status(auth_client, db_session):
    from app.services.backup_crypto import key_path, set_key

    set_key("old")
    key_path().unlink()
    response = auth_client.put("/api/v1/settings/backup-key/recover", json={"key": "old"})
    assert response.status_code == 200
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True


async def test_old_encrypted_record_does_not_authorize_key_recovery(auth_client, db_session):
    from app.models.backup import Backup

    db_session.add(Backup(filename="old-encrypted.json", size_bytes=1, created_by_user_id=1, is_encrypted=True))
    await db_session.commit()
    assert auth_client.put("/api/v1/settings/backup-key/recover", json={"key": "replacement"}).status_code == 409
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


@pytest.mark.parametrize("legacy", [False, True])
async def test_upgrade_allows_plaintext_after_existing_encrypted_records(auth_client, db_session, backup_dir, legacy):
    from app.models.backup import Backup

    db_session.add(Backup(filename="old.json", size_bytes=1, created_by_user_id=1, is_encrypted=True))
    await db_session.commit()
    if legacy:
        backup_dir.mkdir(parents=True, exist_ok=True)
        (backup_dir / "old.json").write_text(base64.b64encode(b'{"version":"1.0"}').decode())
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": False}
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_explicit_encryption_without_global_key_allows_existing_backup_directory(auth_client, db_session, tmp_path):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path)
    await db_session.commit()
    result = auth_client.post("/api/v1/backups/", json={"encrypt": True, "passphrase": "one-off"})
    assert result.status_code == 201
    assert result.json()["is_encrypted"] is True


async def test_old_encrypted_record_can_be_cleared_without_first_calling_status(auth_client, db_session, backup_dir):
    from app.models.backup import Backup

    db_session.add(Backup(filename="old-encrypted.json", size_bytes=1, created_by_user_id=1, is_encrypted=True))
    await db_session.commit()
    assert auth_client.delete("/api/v1/settings/backup-key").json() == {"configured": False}
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_corrupt_old_marker_still_persists_intent(auth_client, db_session):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import intent_path

    intent_path().parent.mkdir(parents=True, exist_ok=True)
    intent_path().write_text("invalid")
    intent_path().chmod(0o600)
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 503
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required


async def test_old_marker_with_key_is_migrated(auth_client, db_session, key_path):
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import set_key

    set_key("existing key")
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True}
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required


async def test_key_lock_fails_closed_when_config_directory_is_missing(auth_client, key_path):
    # A configured installation must retain its config directory for coordination.
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200
    key_path.unlink()
    (key_path.parent / ".backup-key-required").unlink()
    key_path.parent.rmdir()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_old_config_marker_is_recognized_with_external_key(auth_client, db_session, tmp_path, monkeypatch):
    from app.core.config_loader import config_loader
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import _intent_required

    legacy = config_loader.config_path.parent / ".backup-key-required"
    legacy.write_text("required\n")
    legacy.chmod(0o600)
    external = tmp_path / "external" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(external))
    assert _intent_required()
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True, "status": "missing"}
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required


async def test_external_key_default_marker_and_legacy_marker_are_distinct(tmp_path, monkeypatch):
    from app.core.config_loader import config_loader
    from app.services.backup_crypto import intent_path

    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(tmp_path / "other" / "backup.key"))
    assert intent_path().parent == tmp_path / "other"
    assert intent_path() != config_loader.config_path.parent / ".backup-key-required"


async def test_external_key_does_not_ignore_existing_legacy_marker_on_clear(auth_client, db_session, tmp_path, monkeypatch):
    from app.core.config_loader import config_loader

    legacy = config_loader.config_path.parent / ".backup-key-required"
    legacy.write_text("required\n")
    legacy.chmod(0o600)
    external = tmp_path / "external" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(external))
    assert auth_client.get("/api/v1/settings/backup-key").json()["status"] == "missing"
    assert auth_client.put("/api/v1/settings/backup-key/recover", json={"key": "new"}).status_code == 200
    assert auth_client.delete("/api/v1/settings/backup-key").status_code == 200
    assert not legacy.exists()


async def test_key_marker_is_outside_backups_when_external_key_configured(auth_client, db_session, tmp_path, monkeypatch):
    external = tmp_path / "external" / "backup.key"
    external.parent.mkdir()
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(external))
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(external.parent)
    await db_session.commit()
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 400
    assert not external.exists()


async def test_existing_database_intent_with_no_marker_and_no_key_fails_closed(auth_client, db_session, backup_dir):
    from app.models.settings import BackupEncryptionState

    db_session.add(BackupEncryptionState(id=1, required=True))
    await db_session.commit()
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True, "status": "missing"}
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert not backup_dir.exists() or not list(backup_dir.iterdir())


async def test_key_lock_cannot_fail_silently_when_flock_is_unsupported(auth_client, backup_dir, monkeypatch):
    import app.services.backup_crypto as crypto

    def unsupported(*args):
        raise OSError("flock unsupported")
    monkeypatch.setattr(crypto.fcntl, "flock", unsupported)
    response = auth_client.post("/api/v1/backups/", json={})
    assert response.status_code == 500
    assert not backup_dir.exists() or not list(backup_dir.iterdir())


async def test_key_lock_is_not_held_on_readonly_directory_failure(tmp_path, monkeypatch):
    import os

    from app.services import backup_crypto

    external = tmp_path / "external"
    external.mkdir()
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(external / "backup.key"))
    original = os.open

    def fail(path, flags, *args, **kwargs):
        if str(path) == str(external):
            raise PermissionError("unreadable directory")
        return original(path, flags, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(backup_crypto.os, "open", fail)
        with pytest.raises(RuntimeError, match="lock"):
            async with backup_crypto.key_lock():
                pass
    async with backup_crypto.key_lock():
        pass


async def test_external_key_directory_is_created_only_when_setting_key(auth_client, db_session, tmp_path, monkeypatch):
    key = tmp_path / "new" / "nested" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(key))
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": False}
    assert not key.parent.exists()
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200
    assert key.exists()


async def test_key_lock_is_not_held_indefinitely_when_cancelled(tmp_path):
    import asyncio

    from app.services.backup_crypto import key_lock

    async with key_lock():
        async def waiter():
            async with key_lock():
                pass
        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    async with key_lock():
        pass


async def test_key_lock_cannot_replace_legacy_marker_file(auth_client, monkeypatch):
    from app.core.config_loader import config_loader

    legacy = config_loader.config_path.parent / ".backup-key-lock"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(legacy))
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 400


async def test_corrupt_legacy_marker_is_not_hidden_by_valid_new_marker(auth_client, db_session, tmp_path, monkeypatch):
    from app.core.config_loader import config_loader
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import _set_intent

    legacy = config_loader.config_path.parent / ".backup-key-required"
    legacy.write_text("invalid")
    legacy.chmod(0o600)
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(tmp_path / "external" / "backup.key"))
    _set_intent()
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 503
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required


async def test_key_lock_and_marker_follow_external_path(auth_client, db_session, tmp_path, monkeypatch):
    from app.core.config_loader import config_loader
    from app.services.backup_crypto import intent_path

    path = tmp_path / "external" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(path))
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200
    assert intent_path() == path.parent / ".backup-key-required"
    assert intent_path().exists()
    assert not (config_loader.config_path.parent / ".backup-key-required").exists()
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True
    path.unlink()
    intent_path().unlink()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_switching_key_path_does_not_hide_existing_intent(auth_client, db_session, tmp_path, monkeypatch):
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200
    new_key = tmp_path / "other" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(new_key))
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True, "status": "missing"}
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_existing_external_key_with_legacy_marker_works_with_read_only_config(auth_client, db_session, tmp_path, monkeypatch):
    import os

    from app.core.config_loader import config_loader
    from app.services import backup_crypto

    legacy = config_loader.config_path.parent / ".backup-key-required"
    legacy.write_text("required\n")
    legacy.chmod(0o600)
    external = tmp_path / "external" / "backup.key"
    external.parent.mkdir()
    external.write_text("secret")
    external.chmod(0o600)
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(external))
    original = os.open

    def deny_config_writes(path, flags, *args, **kwargs):
        if str(path).startswith(str(legacy.parent / ".backup-key")) and flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
            raise PermissionError("read-only config")
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(backup_crypto.os, "open", deny_config_writes)
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True}
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True


async def test_config_legacy_marker_outside_key_directory_cannot_be_backup_directory(auth_client, db_session, tmp_path, monkeypatch):
    from app.core.config_loader import config_loader

    legacy = config_loader.config_path.parent / ".backup-key-required"
    legacy.write_text("required\n")
    legacy.chmod(0o600)
    external = tmp_path / "external" / "backup.key"
    external.parent.mkdir()
    external.write_text("secret")
    external.chmod(0o600)
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(external))
    assert auth_client.put("/api/v1/settings/global", json={"backup_dir": str(legacy.parent)}).status_code == 400


async def test_clear_migrated_legacy_marker_preserves_fail_closed_on_error(auth_client, db_session, tmp_path, monkeypatch):
    from app.core.config_loader import config_loader
    from app.models.settings import BackupEncryptionState

    legacy = config_loader.config_path.parent / ".backup-key-required"
    legacy.write_text("required\n")
    legacy.chmod(0o600)
    external = tmp_path / "external" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(external))
    assert auth_client.get("/api/v1/settings/backup-key").json()["status"] == "missing"
    assert auth_client.delete("/api/v1/settings/backup-key").json() == {"configured": False}
    assert not legacy.exists()
    db_session.expire_all()
    assert not (await db_session.execute(select(BackupEncryptionState))).scalar_one().required


async def test_clearing_old_key_with_failed_commit_preserves_intent(auth_client, db_session, key_path, monkeypatch):
    import app.api.settings as api
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import set_key

    set_key("existing key")
    original = api.persist_required

    async def fail_clear(db, required):
        if not required:
            raise RuntimeError("failed commit")
        await original(db, required)

    with monkeypatch.context() as patch:
        patch.setattr(api, "persist_required", fail_clear)
        assert auth_client.delete("/api/v1/settings/backup-key").status_code == 500
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_failed_intent_database_write_does_not_remove_key(auth_client, key_path, monkeypatch):
    import app.api.settings as api

    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200
    async def fail(*args):
        raise RuntimeError("database failure")
    with monkeypatch.context() as patch:
        patch.setattr(api, "persist_required", fail)
        assert auth_client.delete("/api/v1/settings/backup-key").status_code == 500
    assert key_path.read_text() == "secret"


async def test_unreadable_existing_key_still_persists_intent(auth_client, db_session, key_path):
    from app.models.settings import BackupEncryptionState

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("secret")
    key_path.chmod(0o644)
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 503
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required
    key_path.unlink()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_key_appearing_after_unconfigured_state_is_detected_before_read(auth_client, db_session, key_path):
    from app.models.settings import BackupEncryptionState

    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": False}
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("secret")
    key_path.chmod(0o644)
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 503
    db_session.expire_all()
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required


async def test_loss_of_intent_marker_with_database_requirement_fails_closed(auth_client, backup_dir, key_path):
    from app.services.backup_crypto import intent_path

    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 200
    intent_path().unlink()
    assert auth_client.get("/api/v1/settings/backup-key").status_code == 500
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert key_path.read_text() == "secret"


async def test_recover_missing_key_requires_admin_and_preserves_encryption(auth_client, api_client, user_headers, backup_dir, key_path):
    settings_url = "/api/v1/settings/backup-key"
    recovery_url = settings_url + "/recover"
    assert auth_client.put(settings_url, json={"key": "old secret"}).status_code == 200
    backup = auth_client.post("/api/v1/backups/", json={}).json()
    key_path.unlink()
    assert api_client.put(recovery_url, headers=user_headers, json={"key": "old secret"}).status_code == 403
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert auth_client.put(recovery_url, json={"key": "old secret"}).json() == {"configured": True}
    assert auth_client.post(f"/api/v1/backups/{backup['id']}/restore", json={}).status_code == 200
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True
    assert auth_client.put(recovery_url, json={"key": "other"}).status_code == 409
    assert key_path.read_text() == "old secret"


async def test_key_recovery_still_requires_admin_when_auth_disabled(api_client, seeded_db, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    assert api_client.put("/api/v1/settings/backup-key/recover", json={"key": "secret"}).status_code == 401


async def test_recovery_success_is_audited_without_key(auth_client, db_session, key_path):
    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "old"}).status_code == 200
    key_path.unlink()
    assert auth_client.put(url + "/recover", json={"key": "recovery secret"}).status_code == 200
    logs = (await db_session.execute(select(AuditLog).where(AuditLog.action == "RECOVER"))).scalars().all()
    assert len(logs) == 1
    assert "recovery secret" not in str(logs[0].__dict__)


async def test_recovery_rejects_unsafe_symlink_without_modifying_it(auth_client, key_path, tmp_path):
    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "old"}).status_code == 200
    key_path.unlink()
    target = tmp_path / "other"
    target.write_text("untouched")
    key_path.symlink_to(target)
    response = auth_client.get(url)
    assert response.status_code == 503
    assert "local operator" in response.json()["detail"].lower()
    assert auth_client.put(url + "/recover", json={"key": "new"}).status_code == 503
    assert key_path.is_symlink()
    assert target.read_text() == "untouched"
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_recovery_rejects_dangling_symlink(auth_client, key_path, tmp_path):
    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "old"}).status_code == 200
    key_path.unlink()
    key_path.symlink_to(tmp_path / "absent")
    response = auth_client.put(url + "/recover", json={"key": "new"})
    assert response.status_code == 503
    assert key_path.is_symlink()


async def test_recovery_restores_missing_key_and_marker(auth_client, key_path):
    from app.services.backup_crypto import intent_path

    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "old"}).status_code == 200
    key_path.unlink()
    intent_path().unlink()
    assert auth_client.put(url + "/recover", json={"key": "replacement"}).json() == {"configured": True}
    assert intent_path().exists()
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True


async def test_recovery_rejects_unsafe_marker_with_local_operator_message(auth_client, key_path):
    from app.services.backup_crypto import intent_path

    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "old"}).status_code == 200
    key_path.unlink()
    intent_path().chmod(0o644)
    response = auth_client.put(url + "/recover", json={"key": "new"})
    assert response.status_code == 503
    assert "local operator" in response.json()["detail"].lower()
    assert not key_path.exists()


async def test_recovery_does_not_replace_file_created_concurrently(auth_client, key_path, monkeypatch):
    import app.services.backup_crypto as crypto

    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "old"}).status_code == 200
    key_path.unlink()
    original = crypto.os.link

    def race(source, destination, **kwargs):
        key_path.write_text("unexpected")
        return original(source, destination, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(crypto.os, "link", race)
        assert auth_client.put(url + "/recover", json={"key": "new"}).status_code == 409
    assert key_path.read_text() == "unexpected"


async def test_recovery_refuses_unconfigured_installation(auth_client):
    assert auth_client.put("/api/v1/settings/backup-key/recover", json={"key": "new"}).status_code == 409


async def test_key_appearing_during_normal_set_is_not_replaced(auth_client, key_path, monkeypatch):
    import app.services.backup_crypto as crypto

    original = crypto.os.link

    def race(source, destination, **kwargs):
        key_path.write_text("unexpected")
        return original(source, destination, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(crypto.os, "link", race)
        response = auth_client.put("/api/v1/settings/backup-key", json={"key": "new"})
    assert response.status_code == 409
    assert key_path.read_text() == "unexpected"


async def test_legacy_import_does_not_make_global_key_configured(auth_client, backup_dir):
    payload = base64.b64encode(b'{"version":"1.0"}')
    assert auth_client.post("/api/v1/backups/upload", files={"file": ("legacy.json", payload)}, data={"allow_legacy_unauthenticated": "true"}).status_code == 201
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": False}
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_legacy_base64_import_requires_separate_import_and_restore_opt_in(auth_client, backup_dir, db_session, seeded_server_and_peer):
    payload = base64.b64encode(json.dumps({"version": "1.0", "servers": []}).encode())
    files = {"file": ("legacy.json", payload, "application/json")}
    url = "/api/v1/backups/upload"
    assert auth_client.post(url, files=files).status_code == 400
    response = auth_client.post(url, files=files, data={"allow_legacy_unauthenticated": "true"})
    assert response.status_code == 201
    backup = response.json()
    assert backup["is_encrypted"] is True
    audit = (await db_session.execute(select(AuditLog).where(AuditLog.action == "IMPORT"))).scalar_one()
    assert audit.details["allow_legacy_unauthenticated"] is True
    assert (backup_dir / backup["filename"]).read_bytes() == payload
    restore = f"/api/v1/backups/{backup['id']}/restore"
    assert auth_client.post(restore, json={"overwrite": True}).status_code == 400
    assert (await db_session.execute(select(Server))).scalars().all()
    assert auth_client.post(restore, json={"overwrite": True, "allow_legacy_unauthenticated": True}).status_code == 200


async def test_list_classifies_backup_files_without_exposing_contents(auth_client, backup_dir):
    plain = auth_client.post("/api/v1/backups/", json={}).json()
    encrypted = auth_client.post("/api/v1/backups/", json={"encrypt": True, "passphrase": "password"}).json()
    payload = base64.b64encode(b'{"version":"1.0","secret":"private-backup-data"}')
    legacy = auth_client.post("/api/v1/backups/upload", files={"file": ("legacy.json", payload)}, data={"allow_legacy_unauthenticated": "true"}).json()
    response = auth_client.get("/api/v1/backups/")
    assert response.status_code == 200
    rows = {item["id"]: item for item in response.json()}
    assert rows[plain["id"]]["is_legacy_unauthenticated"] is False
    assert rows[encrypted["id"]]["is_legacy_unauthenticated"] is False
    assert rows[encrypted["id"]]["is_encrypted_format"] is True
    assert rows[legacy["id"]]["is_legacy_unauthenticated"] is True
    assert rows[legacy["id"]]["is_encrypted"] is False
    assert rows[legacy["id"]]["is_encrypted_format"] is False
    assert rows[encrypted["id"]]["is_encrypted"] is None
    assert "private-backup-data" not in response.text
    (backup_dir / encrypted["filename"]).write_text('{"format":"broken"}')
    (backup_dir / plain["filename"]).unlink()
    rows = {item["id"]: item for item in auth_client.get("/api/v1/backups/").json()}
    assert rows[encrypted["id"]]["is_legacy_unauthenticated"] is None
    assert rows[plain["id"]]["is_legacy_unauthenticated"] is None
    assert rows[encrypted["id"]]["is_encrypted"] is None
    assert rows[plain["id"]]["is_encrypted"] is None
    assert rows[encrypted["id"]]["is_encrypted_format"] is None
    assert rows[plain["id"]]["is_encrypted_format"] is None


async def test_list_detects_base64_independent_of_encrypted_metadata(auth_client, backup_dir, db_session):
    from app.models.backup import Backup

    backup = auth_client.post("/api/v1/backups/", json={}).json()
    (backup_dir / backup["filename"]).write_text(base64.b64encode(b'{"version":"1.0"}').decode())
    row = (await db_session.execute(select(Backup).where(Backup.id == backup["id"]))).scalar_one()
    assert not row.is_encrypted
    listed = auth_client.get("/api/v1/backups/").json()[0]
    assert listed["is_legacy_unauthenticated"] is True


async def test_list_handles_unsafe_backup_path_as_unknown(auth_client, backup_dir, tmp_path):
    backup = auth_client.post("/api/v1/backups/", json={}).json()
    path = backup_dir / backup["filename"]
    path.unlink()
    target = tmp_path / "other"
    target.write_text(base64.b64encode(b'{"version":"1.0"}').decode())
    path.symlink_to(target)
    assert auth_client.get("/api/v1/backups/").json()[0]["is_legacy_unauthenticated"] is None


async def test_list_does_not_read_backup_outside_directory(auth_client, backup_dir, tmp_path, db_session):
    from app.models.backup import Backup

    secret_file = tmp_path / "outside.json"
    secret_file.write_text(base64.b64encode(b'{"version":"1.0"}').decode())
    db_session.add(Backup(filename="../outside.json", size_bytes=1, created_by_user_id=1, is_encrypted=True))
    await db_session.commit()
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_legacy_unauthenticated"] is None
    assert item["is_encrypted"] is None


async def test_list_handles_fifo_as_unknown(auth_client, backup_dir):
    import os

    backup = auth_client.post("/api/v1/backups/", json={}).json()
    path = backup_dir / backup["filename"]
    path.unlink()
    os.mkfifo(path)
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_legacy_unauthenticated"] is None
    assert item["is_encrypted"] is None


async def test_list_handles_oversized_backup_as_unknown(auth_client, backup_dir):
    backup = auth_client.post("/api/v1/backups/", json={}).json()
    with (backup_dir / backup["filename"]).open("wb") as file:
        file.truncate(16 * 1024 * 1024 + 1)
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_legacy_unauthenticated"] is None
    assert item["is_encrypted"] is None


async def test_list_directory_failure_returns_unknown(auth_client, backup_dir, monkeypatch):
    from app.services.settings_service import SettingsService

    auth_client.post("/api/v1/backups/", json={})
    async def fail(*args):
        raise OSError("private system path")
    monkeypatch.setattr(SettingsService, "get_backup_dir", fail)
    response = auth_client.get("/api/v1/backups/")
    assert response.status_code == 200
    assert response.json()[0]["is_legacy_unauthenticated"] is None
    assert "private system path" not in response.text


async def test_list_file_classification_does_not_block_event_loop(db_session, seeded_db, tmp_path, monkeypatch):
    import asyncio
    import threading

    import app.api.backup as module
    from app.models.backup import Backup
    from app.services.settings_service import SettingsService

    db_session.add(Backup(filename="dummy.json", size_bytes=1, created_by_user_id=1))
    await db_session.commit()
    started, release = threading.Event(), threading.Event()

    def slow(*args):
        started.set()
        if not release.wait(2):
            raise RuntimeError("event loop was blocked")
        return None, None

    monkeypatch.setattr(module, "backup_file_status", slow)
    task = asyncio.create_task(module.list_backups(skip=0, limit=100, db=db_session, current_user=None, settings_service=SettingsService()))
    try:
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert started.is_set()
        release.set()
        assert (await asyncio.wait_for(task, 5))[0]["is_encrypted"] is None
    finally:
        release.set()


async def test_list_does_not_trust_plaintext_version_as_encrypted(auth_client, backup_dir):
    backup = auth_client.post("/api/v1/backups/", json={"encrypt": True, "passphrase": "pw"}).json()
    (backup_dir / backup["filename"]).write_text('{"version":"1.0","secret":"private"}')
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_legacy_unauthenticated"] is False
    assert item["is_encrypted"] is False


async def test_list_does_not_run_kdf_or_claim_envelope_authentication(auth_client, backup_dir, monkeypatch):
    import app.services.backup_service as module

    auth_client.put("/api/v1/settings/backup-key", json={"key": "global"})
    backup = auth_client.post("/api/v1/backups/", json={}).json()
    path = backup_dir / backup["filename"]
    monkeypatch.setattr(module, "decrypt_backup", lambda *args: (_ for _ in ()).throw(AssertionError("listing invoked KDF")))
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_encrypted"] is None
    assert item["is_encrypted_format"] is True
    envelope = json.loads(path.read_text())
    envelope["ciphertext"] = base64.b64encode(b"plain-looking-data" * 3).decode()
    path.write_text(json.dumps(envelope))
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_encrypted"] is None
    assert item["is_legacy_unauthenticated"] is False
    assert item["is_encrypted_format"] is True


async def test_list_uses_structural_classification_even_when_server_key_is_missing(auth_client, backup_dir, key_path):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "global"})
    auth_client.post("/api/v1/backups/", json={})
    key_path.unlink()
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_encrypted"] is None
    assert item["is_encrypted_format"] is True


async def test_list_rejects_encrypted_envelope_containing_invalid_backup(auth_client, backup_dir):
    from app.services.backup_crypto import encrypt_backup

    auth_client.put("/api/v1/settings/backup-key", json={"key": "global"})
    backup = auth_client.post("/api/v1/backups/", json={}).json()
    (backup_dir / backup["filename"]).write_text(encrypt_backup("not a backup", "global"))
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_encrypted"] is None
    assert item["is_legacy_unauthenticated"] is False


async def test_list_does_not_authenticate_envelope_with_untrusted_key_file(auth_client, backup_dir, key_path):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "global"})
    auth_client.post("/api/v1/backups/", json={})
    key_path.chmod(0o644)
    item = auth_client.get("/api/v1/backups/").json()[0]
    assert item["is_legacy_unauthenticated"] is False
    assert item["is_encrypted"] is None


async def test_normal_put_cannot_bypass_missing_key_recovery(auth_client, db_session, key_path):
    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "old"}).status_code == 200
    key_path.unlink()
    response = auth_client.put(url, json={"key": "replacement"})
    assert response.status_code == 409
    assert not key_path.exists()
    assert auth_client.put(url + "/recover", json={"key": "replacement"}).status_code == 200
    assert len((await db_session.execute(select(AuditLog).where(AuditLog.action == "RECOVER"))).scalars().all()) == 1


async def test_normal_put_cannot_bypass_missing_legacy_key_before_migration(auth_client, key_path):
    from app.services.backup_crypto import set_key

    set_key("old")
    key_path.unlink()
    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "new"}).status_code == 409
    assert not key_path.exists()
    assert auth_client.put(url + "/recover", json={"key": "new"}).status_code == 200


async def test_legacy_import_rejects_malformed_base64_without_writes(auth_client, backup_dir):
    for payload in (b"!!!", base64.b64encode(b'{"format":"broken","version":1}'), base64.b64encode(b'{}'), base64.b64encode(b'{"version":"1.0","servers":{}}')):
        response = auth_client.post("/api/v1/backups/upload", files={"file": ("legacy.json", payload)}, data={"allow_legacy_unauthenticated": "true"})
        assert response.status_code == 400
    assert not backup_dir.exists() or not list(backup_dir.iterdir())


async def test_bad_legacy_upload_errors_do_not_echo_file_contents(auth_client, backup_dir):
    response = auth_client.post("/api/v1/backups/upload", files={"file": ("legacy.json", b"sensitive-input!")}, data={"allow_legacy_unauthenticated": "true"})
    assert response.status_code == 400
    assert "sensitive-input" not in response.text


async def test_invalid_unicode_upload_is_a_safe_client_error(auth_client, backup_dir):
    response = auth_client.post("/api/v1/backups/upload", files={"file": ("legacy.json", b"\xff\xfe")}, data={"allow_legacy_unauthenticated": "true"})
    assert response.status_code == 400


async def test_loss_of_files_after_failed_first_write_still_blocks_backups(auth_client, db_session, key_path, monkeypatch):
    import app.services.backup_crypto as crypto

    crypto._set_intent()
    with monkeypatch.context() as patch:
        patch.setattr(crypto.os, "link", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk error")))
        assert auth_client.put("/api/v1/settings/backup-key/recover", json={"key": "secret"}).status_code == 500
    crypto.intent_path().unlink()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_old_key_without_marker_is_adopted_before_file_loss(auth_client, db_session, key_path):
    from app.models.settings import BackupEncryptionState

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("old key")
    key_path.chmod(0o600)
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True}
    state = (await db_session.execute(select(BackupEncryptionState))).scalar_one()
    assert state.required is True


async def test_old_encrypted_backup_record_does_not_imply_global_key(auth_client, db_session, backup_dir):
    from app.models.backup import Backup

    db_session.add(Backup(filename="old-encrypted.json", size_bytes=1, created_by_user_id=1, is_encrypted=True))
    await db_session.commit()
    response = auth_client.post("/api/v1/backups/", json={})
    assert response.status_code == 201
    assert response.json()["is_encrypted"] is False


async def test_old_encrypted_metadata_does_not_enable_global_intent(auth_client, db_session, backup_dir):
    from app.models.backup import Backup

    db_session.add(Backup(filename="old-encrypted.json", size_bytes=1, created_by_user_id=1, is_encrypted=True))
    await db_session.commit()
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": False}
    backup = (await db_session.execute(select(Backup))).scalar_one()
    await db_session.delete(backup)
    await db_session.commit()
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_old_encrypted_record_with_available_key_is_adopted(auth_client, db_session, backup_dir, key_path):
    from app.models.backup import Backup

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("old key")
    key_path.chmod(0o600)
    db_session.add(Backup(filename="old-encrypted.json", size_bytes=1, created_by_user_id=1, is_encrypted=True))
    await db_session.commit()
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True}
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True


async def test_import_of_explicitly_encrypted_backup_does_not_enable_global_intent(auth_client, backup_dir):
    response = auth_client.post("/api/v1/backups/", json={"encrypt": True, "passphrase": "one-off"})
    assert response.status_code == 201
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": False}
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_existing_unmarked_key_is_adopted_before_failed_rotation(auth_client, db_session, key_path, monkeypatch):
    import app.services.backup_crypto as crypto
    from app.models.settings import BackupEncryptionState

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("old key")
    key_path.chmod(0o600)
    with monkeypatch.context() as patch:
        patch.setattr(crypto.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk error")))
        assert auth_client.put("/api/v1/settings/backup-key", json={"key": "new"}).status_code == 500
    assert key_path.read_text() == "old key"
    # A failed adoption leaves the original key intact; retry records intent.
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": True}
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required
    key_path.unlink()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_key_state_survives_failed_encrypted_backup_creation(auth_client, db_session, key_path, monkeypatch):
    import app.services.backup_service as module
    from app.models.settings import BackupEncryptionState
    from app.services.backup_crypto import intent_path

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("old key")
    key_path.chmod(0o600)
    with monkeypatch.context() as patch:
        patch.setattr(module, "encrypt_backup", lambda *args: (_ for _ in ()).throw(RuntimeError("crypto error")))
        assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    key_path.unlink()
    intent_path().unlink()
    assert (await db_session.execute(select(BackupEncryptionState))).scalar_one().required
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_failed_database_commit_during_key_clear_blocks_backups(auth_client, backup_dir, monkeypatch):
    import app.api.settings as settings_api

    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "secret"}).status_code == 200
    original = settings_api.persist_required

    async def fail_clear(db, required):
        if not required:
            raise RuntimeError("database failure")
        await original(db, required)

    with monkeypatch.context() as patch:
        patch.setattr(settings_api, "persist_required", fail_clear)
        assert auth_client.delete(url).status_code == 500
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_missing_intent_table_fails_closed(auth_client, api_db, backup_dir):
    from app.models.settings import BackupEncryptionState

    async with api_db.engine.begin() as conn:
        await conn.run_sync(BackupEncryptionState.__table__.drop)
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert not backup_dir.exists() or not list(backup_dir.iterdir())


async def test_existing_database_schema_gets_new_state_table(api_db):
    from sqlalchemy import inspect

    from app.core.database import Base
    from app.models.settings import BackupEncryptionState

    async with api_db.engine.begin() as conn:
        await conn.run_sync(BackupEncryptionState.__table__.drop)
        await conn.run_sync(Base.metadata.create_all)
        assert await conn.run_sync(lambda sync: inspect(sync).has_table("backup_encryption_state"))


@pytest.mark.parametrize("method,path,body", [
    ("put", "/api/v1/settings/backup-key", {"key": ["sensitive input"]}),
    ("post", "/api/v1/backups/", {"passphrase": ["sensitive input"]}),
    ("post", "/api/v1/backups/1/restore", {"passphrase": ["sensitive input"]}),
])
async def test_validation_does_not_echo_secret_inputs(auth_client, method, path, body):
    response = getattr(auth_client, method)(path, json=body)
    assert response.status_code == 422
    assert "sensitive input" not in response.text


async def test_json_body_overwrite_replaces_existing_records(auth_client, db_session, seeded_server_and_peer):
    from backup_helpers import as_upload, make_backup_payload

    uploaded = auth_client.post("/api/v1/backups/upload", files=as_upload(make_backup_payload())).json()
    response = auth_client.post(f"/api/v1/backups/{uploaded['id']}/restore", json={"overwrite": True})
    assert response.status_code == 200
    assert response.json()["details"]["cleared_existing"] is True
    assert (await db_session.execute(select(Server.name))).scalars().all() == ["restored-server"]


async def test_encrypted_record_rejects_plaintext_fallback(auth_client, backup_dir, seeded_server_and_peer, db_session):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"})
    created = auth_client.post("/api/v1/backups/", json={}).json()
    (backup_dir / created["filename"]).write_text(json.dumps({"version": "1.0", "servers": []}))
    response = auth_client.post(f"/api/v1/backups/{created['id']}/restore", json={"overwrite": True})
    assert response.status_code == 400
    assert (await db_session.execute(select(Server))).scalars().all()


async def test_key_file_must_not_live_in_backup_directory(auth_client, backup_dir, key_path, monkeypatch):
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(backup_dir / "backup.key"))
    response = auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"})
    assert response.status_code == 400
    assert not (backup_dir / "backup.key").exists()


async def test_key_file_cannot_replace_sqlite_database(tmp_path, monkeypatch):
    from app.services.backup_crypto import validate_key_location

    database_path = tmp_path / "database.sqlite"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(database_path))
    with pytest.raises(ValueError, match="separate from the database"):
        validate_key_location(tmp_path / "backups", f"sqlite+aiosqlite:///{database_path}")


async def test_missing_configured_key_never_creates_plaintext(auth_client, backup_dir, key_path):
    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "secret"}).status_code == 200
    key_path.unlink()
    assert auth_client.get(url).json() == {"configured": True, "status": "missing"}
    response = auth_client.post("/api/v1/backups/", json={})
    assert response.status_code == 500
    assert not backup_dir.exists() or not list(backup_dir.iterdir())
    assert auth_client.delete(url).status_code == 200
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_missing_parent_directory_does_not_remove_encryption_intent(auth_client, backup_dir, key_path, tmp_path, monkeypatch):
    separate_key = tmp_path / "separate" / "backup.key"
    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(separate_key))
    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "secret"}).status_code == 200
    separate_key.unlink()
    (separate_key.parent / ".backup-key-required").unlink()
    separate_key.parent.rmdir()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_loss_of_both_key_and_marker_does_not_downgrade(auth_client, backup_dir, key_path):
    from app.services.backup_crypto import intent_path

    url = "/api/v1/settings/backup-key"
    assert auth_client.put(url, json={"key": "secret"}).status_code == 200
    key_path.unlink()
    intent_path().unlink()
    assert auth_client.get(url).json() == {"configured": True, "status": "missing"}
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert not backup_dir.exists() or not list(backup_dir.iterdir())
    assert auth_client.delete(url).status_code == 200
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_existing_unmarked_key_is_adopted_before_backup(auth_client, backup_dir, key_path):
    from app.services.backup_crypto import intent_path

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("existing key")
    key_path.chmod(0o600)
    assert not intent_path().exists()
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is True
    assert intent_path().exists()
    key_path.unlink()
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500


async def test_encrypted_record_rejects_base64_downgrade_by_default(auth_client, backup_dir, seeded_server_and_peer, db_session):
    auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"})
    backup = auth_client.post("/api/v1/backups/", json={}).json()
    payload = base64.b64encode(json.dumps({"version": "1.0", "servers": []}).encode()).decode()
    (backup_dir / backup["filename"]).write_text(payload)
    response = auth_client.post(f"/api/v1/backups/{backup['id']}/restore", json={"overwrite": True})
    assert response.status_code == 400
    assert (await db_session.execute(select(Server))).scalars().all()
    response = auth_client.post(f"/api/v1/backups/{backup['id']}/restore", json={"overwrite": True, "allow_legacy_unauthenticated": True})
    assert response.status_code == 200


async def test_backup_endpoints_require_real_admin_even_if_auth_disabled(api_client, seeded_db, db_session, admin_headers, user_headers):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    assert api_client.post("/api/v1/backups/", json={}).status_code == 401
    assert api_client.post("/api/v1/backups/", headers=user_headers, json={}).status_code == 403
    assert api_client.post("/api/v1/backups/", headers=admin_headers, json={}).status_code == 201


@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/backups/"),
    ("get", "/api/v1/backups/1"),
    ("get", "/api/v1/backups/1/download"),
    ("post", "/api/v1/backups/1/restore"),
    ("post", "/api/v1/backups/upload"),
    ("delete", "/api/v1/backups/1"),
    ("get", "/api/v1/backups/stats/summary"),
])
async def test_all_backup_routes_require_admin(api_client, seeded_db, db_session, method, path, user_headers):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    assert getattr(api_client, method)(path).status_code == 401
    assert getattr(api_client, method)(path, headers=user_headers).status_code == 403


def test_default_key_is_gitignored():
    import shutil
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    if not shutil.which("git") or not (root / ".git").exists():
        pytest.skip("Git repository unavailable")
    result = subprocess.run(["git", "check-ignore", "backend/backup.key"], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0


def test_default_key_gitignore_check_skips_without_git(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(pytest.skip.Exception):
        test_default_key_is_gitignored()


def test_default_key_gitignore_check_skips_without_repository(monkeypatch):
    from pathlib import Path

    original = Path.exists
    def exists(path):
        return False if path.name == ".git" else original(path)
    monkeypatch.setattr(Path, "exists", exists)
    with pytest.raises(pytest.skip.Exception):
        test_default_key_is_gitignored()


async def test_rotation_waits_until_backup_file_is_written(db_session, seeded_db, tmp_path, key_path, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    import app.services.backup_service as module
    from app.services.backup_crypto import decrypt_backup, key_lock, set_key
    from app.services.backup_service import BackupService

    class Settings:
        async def get_backup_dir(self, db):
            return str(tmp_path / "backups")

    set_key("old key")
    entered, release, rotated = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def publish(*args, **kwargs):
        entered.set()
        await release.wait()

    monkeypatch.setattr(module.event_bus, "publish", AsyncMock(side_effect=publish))
    service = BackupService(Settings())
    creation = asyncio.create_task(service.create_backup(db_session, user_id=1))
    await asyncio.wait_for(entered.wait(), 5)

    async def rotate():
        async with key_lock():
            set_key("new key")
        rotated.set()

    rotation = asyncio.create_task(rotate())
    await asyncio.sleep(0.15)
    assert not rotated.is_set()
    release.set()
    backup = await asyncio.wait_for(creation, 5)
    await asyncio.wait_for(rotation, 5)
    envelope = json.loads((tmp_path / "backups" / backup.filename).read_text())
    assert json.loads(decrypt_backup(envelope, "old key"))["version"] == "1.0"
    assert key_path.read_text() == "new key"


@pytest.mark.parametrize("operation", ["encrypt", "decrypt"])
async def test_crypto_runs_off_event_loop_and_backup_lock_survives(db_session, seeded_db, tmp_path, monkeypatch, operation):
    import asyncio
    import threading

    import app.services.backup_service as module
    from app.services.backup_crypto import key_lock, set_key
    from app.services.backup_service import BackupService

    class Settings:
        async def get_backup_dir(self, db):
            return str(tmp_path / "backups")

    set_key("secret")
    service = BackupService(Settings())
    backup = await service.create_backup(db_session, user_id=1) if operation == "decrypt" else None
    original = getattr(module, operation + "_backup")
    started, release = threading.Event(), threading.Event()

    def slow(*args):
        started.set()
        if not release.wait(2):
            raise RuntimeError("event loop was blocked")
        return original(*args)

    monkeypatch.setattr(module, operation + "_backup", slow)
    task = asyncio.create_task(service.create_backup(db_session, user_id=1) if operation == "encrypt" else service.restore_backup(db_session, backup.id, user_id=1))
    try:
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert started.is_set()
        if operation == "encrypt":
            acquired = asyncio.Event()

            async def rotate():
                async with key_lock():
                    acquired.set()

            rotation = asyncio.create_task(rotate())
            await asyncio.sleep(0.1)
            assert not acquired.is_set()
        release.set()
        await asyncio.wait_for(task, 5)
        if operation == "encrypt":
            await asyncio.wait_for(rotation, 5)
    finally:
        release.set()


async def test_cancelled_backup_keeps_key_lock_until_crypto_worker_finishes(db_session, seeded_db, tmp_path, monkeypatch):
    import asyncio
    import threading

    import app.services.backup_service as module
    from app.services.backup_crypto import key_lock, set_key
    from app.services.backup_service import BackupService

    class Settings:
        async def get_backup_dir(self, db):
            return str(tmp_path / "backups")

    set_key("secret")
    started, release = threading.Event(), threading.Event()
    original = module.encrypt_backup

    def slow(*args):
        started.set()
        release.wait(5)
        return original(*args)

    monkeypatch.setattr(module, "encrypt_backup", slow)
    task = asyncio.create_task(BackupService(Settings()).create_backup(db_session, user_id=1))
    for _ in range(100):
        if started.is_set():
            break
        await asyncio.sleep(0.01)
    assert started.is_set()
    task.cancel()
    acquired = asyncio.Event()

    async def lock():
        async with key_lock():
            acquired.set()

    waiting = asyncio.create_task(lock())
    try:
        await asyncio.sleep(0.1)
        assert not acquired.is_set()
        task.cancel()
        await asyncio.sleep(0.1)
        assert not acquired.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(waiting, 5)
    finally:
        release.set()


async def test_cancelled_backup_worker_failure_does_not_skip_lock_cleanup(db_session, seeded_db, tmp_path, monkeypatch):
    import asyncio
    import threading

    import app.services.backup_service as module
    from app.services.backup_crypto import key_lock, set_key
    from app.services.backup_service import BackupService

    set_key("secret")
    started, release = threading.Event(), threading.Event()

    def fail(*args):
        started.set()
        release.wait(5)
        raise RuntimeError("worker error")

    monkeypatch.setattr(module, "encrypt_backup", fail)
    task = asyncio.create_task(BackupService().create_backup(db_session, user_id=1))
    for _ in range(100):
        if started.is_set():
            break
        await asyncio.sleep(0.01)
    assert started.is_set()
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with key_lock():
        pass


async def test_key_lock_is_not_held_after_non_cancelled_crypto_error(db_session, seeded_db, monkeypatch):
    import app.services.backup_service as module
    from app.services.backup_crypto import key_lock, set_key
    from app.services.backup_service import BackupService

    set_key("secret")
    monkeypatch.setattr(module, "encrypt_backup", lambda *args: (_ for _ in ()).throw(RuntimeError("failure")))
    with pytest.raises(RuntimeError, match="failure"):
        await BackupService().create_backup(db_session, user_id=1)
    async with key_lock():
        pass


def test_key_lock_serializes_other_processes(tmp_path):
    import fcntl
    import os
    import subprocess
    import sys

    from app.services.backup_crypto import intent_path

    lock = intent_path().parent
    lock.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        code = "import fcntl,os,sys; f=os.open(sys.argv[1],os.O_RDONLY); fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)"
        result = subprocess.run([sys.executable, "-c", code, str(lock)], capture_output=True)
        assert result.returncode != 0
    finally:
        os.close(fd)


async def test_legacy_opt_in_needs_no_fake_passphrase(auth_client, backup_dir, key_path):
    backup = auth_client.post("/api/v1/backups/", json={"encrypt": True, "passphrase": "secret"}).json()
    (backup_dir / backup["filename"]).write_text(base64.b64encode(b'{"version":"1.0"}').decode())
    response = auth_client.post(f"/api/v1/backups/{backup['id']}/restore", json={"allow_legacy_unauthenticated": True})
    assert response.status_code == 200


async def test_legacy_opt_in_is_recorded_in_audit(auth_client, backup_dir, db_session):
    backup = auth_client.post("/api/v1/backups/", json={"encrypt": True, "passphrase": "secret"}).json()
    (backup_dir / backup["filename"]).write_text(base64.b64encode(b'{"version":"1.0"}').decode())
    assert auth_client.post(f"/api/v1/backups/{backup['id']}/restore", json={"allow_legacy_unauthenticated": True}).status_code == 200
    audit = (await db_session.execute(select(AuditLog).where(AuditLog.action == "RESTORE"))).scalar_one()
    assert audit.details["allow_legacy_unauthenticated"] is True


async def test_failed_first_key_install_remains_fail_closed(auth_client, backup_dir, monkeypatch):
    import app.services.backup_crypto as crypto

    original = crypto.os.link

    def fail_key_replace(source, dest, **kwargs):
        if dest == crypto.key_path():
            raise OSError("disk error")
        return original(source, dest, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(crypto.os, "link", fail_key_replace)
        assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 500
    assert auth_client.post("/api/v1/backups/", json={}).status_code == 500
    assert auth_client.delete("/api/v1/settings/backup-key").status_code == 200
    assert auth_client.post("/api/v1/backups/", json={}).json()["is_encrypted"] is False


async def test_key_cannot_overwrite_encryption_intent(auth_client, monkeypatch):
    from app.services.backup_crypto import intent_path

    monkeypatch.setenv("LINGUARD_BACKUP_KEY_PATH", str(intent_path()))
    assert auth_client.put("/api/v1/settings/backup-key", json={"key": "secret"}).status_code == 400


async def test_key_cannot_be_hardlinked_to_configuration(auth_client, key_path):
    import os

    from app.core.config_loader import config_loader

    key_path.parent.mkdir(parents=True, exist_ok=True)
    config_loader.config_path.write_text("existing config")
    config_loader.config_path.chmod(0o600)
    os.link(config_loader.config_path, key_path)
    assert auth_client.delete("/api/v1/settings/backup-key").status_code == 503
    assert config_loader.config_path.read_text() == "existing config"
    assert key_path.exists()


async def test_key_write_errors_do_not_echo_secret_paths(auth_client, key_path, monkeypatch):
    import app.services.backup_crypto as crypto

    secret = "secret-in-error"
    monkeypatch.setattr(crypto.os, "replace", lambda *args: (_ for _ in ()).throw(OSError(secret)))
    response = auth_client.put("/api/v1/settings/backup-key", json={"key": secret})
    assert response.status_code == 500
    assert secret not in response.text
