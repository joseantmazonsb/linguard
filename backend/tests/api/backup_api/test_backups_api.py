"""Tests for ``app/api/backup.py``.

All tests exercise the HTTP API against a real SQLite database; the backup
directory is redirected to ``tmp_path`` (see ``conftest.py``) so the real
backup files are written and read from a temporary directory.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from backup_helpers import as_upload, make_backup_payload
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.backup import Backup
from app.models.settings import GlobalSettings


async def _audit_actions(db_session):
    result = await db_session.execute(select(AuditLog.action))
    return [row[0] for row in result.all()]


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def test_should_reject_requested_encryption_without_key(auth_client, backup_dir):
    response = auth_client.post("/api/v1/backups/", json={"encrypt": True})
    assert response.status_code == 400
    assert "passphrase" in response.json()["detail"].lower()
    assert not backup_dir.exists() or list(backup_dir.iterdir()) == []

async def test_should_create_backup_when_configuration_exists(
    auth_client, backup_dir, seeded_server_and_peer, db_session
):
    response = auth_client.post("/api/v1/backups/", json={"description": "nightly"})

    assert response.status_code == 201
    body = response.json()
    assert body["description"] == "nightly"
    assert body["servers_count"] == 1
    assert body["peers_count"] == 1
    assert body["created_by_username"] == "admin"
    assert body["is_encrypted"] is False
    assert body["filename"].endswith(".json")

    # The file was really written to the configured backup directory...
    file_path = backup_dir / body["filename"]
    assert file_path.exists()
    assert body["file_size"] == file_path.stat().st_size

    # ...and contains the server and peer data.
    document = json.loads(file_path.read_text())
    assert document["version"] == "1.0"
    assert [s["name"] for s in document["servers"]] == ["srv-main"]
    assert [p["name"] for p in document["peers"]] == ["peer-main"]

    # The metadata row is persisted.
    result = await db_session.execute(select(Backup))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].filename == body["filename"]
    assert rows[0].created_by_user_id == body["created_by_id"]

    # Creating a backup is audited.
    assert "CREATE" in await _audit_actions(db_session)


async def test_should_create_empty_backup_when_no_configuration(
    auth_client, backup_dir
):
    response = auth_client.post("/api/v1/backups/", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["servers_count"] == 0
    assert body["peers_count"] == 0
    assert body["description"] is None

    document = json.loads((backup_dir / body["filename"]).read_text())
    assert document["servers"] == []
    assert document["peers"] == []


async def test_should_return_500_when_backup_dir_is_not_a_directory(
    auth_client, backup_dir, db_session, tmp_path
):
    # A regular file where the directory should be makes the filesystem write fail.
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(blocker)
    await db_session.commit()

    response = auth_client.post("/api/v1/backups/", json={})

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Failed to create backup:")


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------

async def test_should_list_backups_when_multiple_exist(auth_client, backup_dir):
    first = auth_client.post("/api/v1/backups/", json={"description": "first"}).json()
    second = auth_client.post("/api/v1/backups/", json={"description": "second"}).json()

    response = auth_client.get("/api/v1/backups/")

    assert response.status_code == 200
    body = response.json()
    assert {b["id"] for b in body} == {first["id"], second["id"]}
    assert {b["created_by_username"] for b in body} == {"admin"}
    assert all(b["created_at"] for b in body)

    limited = auth_client.get("/api/v1/backups/", params={"skip": 1, "limit": 1})
    assert len(limited.json()) == 1

    empty = auth_client.get("/api/v1/backups/", params={"skip": 10})
    assert empty.json() == []


async def test_should_get_backup_by_id_when_it_exists(auth_client, backup_dir):
    created = auth_client.post("/api/v1/backups/", json={"description": "keep"}).json()

    response = auth_client.get(f"/api/v1/backups/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["filename"] == created["filename"]
    assert body["description"] == "keep"
    assert body["size_bytes"] == created["file_size"]


async def test_should_return_404_when_backup_does_not_exist(auth_client, backup_dir):
    assert auth_client.get("/api/v1/backups/4242").status_code == 404
    assert auth_client.delete("/api/v1/backups/4242").status_code == 404
    assert auth_client.post("/api/v1/backups/4242/restore").status_code == 404
    assert auth_client.get("/api/v1/backups/4242/download").status_code == 404


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

async def test_should_download_backup_file_when_it_exists_on_disk(
    auth_client, backup_dir
):
    created = auth_client.post("/api/v1/backups/", json={}).json()

    response = auth_client.get(f"/api/v1/backups/{created['id']}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "attachment" in response.headers["content-disposition"]
    assert "wireguard-backup-" in response.headers["content-disposition"]
    document = json.loads(response.content)
    assert document["version"] == "1.0"


async def test_should_return_404_when_downloading_backup_whose_file_is_gone(
    auth_client, backup_dir
):
    created = auth_client.post("/api/v1/backups/", json={}).json()
    os.unlink(backup_dir / created["filename"])

    response = auth_client.get(f"/api/v1/backups/{created['id']}/download")

    assert response.status_code == 404
    assert response.json()["detail"] == "Backup file not found on disk"


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

async def test_should_upload_backup_when_file_is_valid(auth_client, backup_dir, db_session):
    response = auth_client.post(
        "/api/v1/backups/upload",
        files=as_upload(make_backup_payload()),
        data={"description": "uploaded"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["description"] == "uploaded"
    assert body["servers_count"] == 1
    assert body["peers_count"] == 1
    assert body["is_encrypted"] is False

    stored = backup_dir / body["filename"]
    assert stored.exists()
    assert json.loads(stored.read_text())["version"] == "1.0"

    actions = await _audit_actions(db_session)
    assert "IMPORT" in actions


async def test_should_default_upload_description_when_not_given(auth_client, backup_dir):
    response = auth_client.post(
        "/api/v1/backups/upload",
        files=as_upload(make_backup_payload(), filename="my-backup.json"),
    )

    assert response.status_code == 201
    assert response.json()["description"] == "Imported from my-backup.json"


async def test_should_reject_upload_when_json_is_malformed(auth_client, backup_dir):
    response = auth_client.post(
        "/api/v1/backups/upload", files=as_upload("{not json")
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail.startswith("Invalid backup file:")
    assert "Invalid JSON format" in detail
    assert not backup_dir.exists() or list(backup_dir.glob("*")) == []


async def test_should_reject_upload_when_version_is_missing(auth_client, backup_dir):
    payload = make_backup_payload()
    payload.pop("version")

    response = auth_client.post("/api/v1/backups/upload", files=as_upload(payload))

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid backup file: Invalid backup file: missing version"


async def test_should_return_500_when_upload_cannot_write_backup_file(
    auth_client, backup_dir, db_session, tmp_path
):
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(blocker)
    await db_session.commit()

    response = auth_client.post(
        "/api/v1/backups/upload", files=as_upload(make_backup_payload())
    )

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Failed to upload backup:")


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

async def test_should_reject_malicious_imported_settings_without_overwriting_configuration(
    auth_client, backup_dir, db_session, seeded_server_and_peer
):
    from app.models.server import Server

    payload = make_backup_payload()
    payload["global_settings"].update({
        "setup_completed": False, "disable_auth": True, "secret_key": "attacker-secret"
    })
    uploaded = auth_client.post("/api/v1/backups/upload", files=as_upload(payload)).json()
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    original = (settings.setup_completed, settings.disable_auth, settings.secret_key,
                settings.dns_primary)
    response = auth_client.post(f"/api/v1/backups/{uploaded['id']}/restore", params={"overwrite": "true"})
    assert response.status_code == 400
    assert "global_settings" in response.json()["detail"]
    await db_session.refresh(settings)
    assert (settings.setup_completed, settings.disable_auth, settings.secret_key,
            settings.dns_primary) == original
    names = (await db_session.execute(select(Server.name))).scalars().all()
    assert names == ["srv-main"]

async def test_should_return_400_for_missing_bounce_target(auth_client, backup_dir):
    payload = make_backup_payload()
    payload["servers"][0]["bounce_via_server_id"] = 999
    uploaded = auth_client.post("/api/v1/backups/upload", files=as_upload(payload)).json()
    response = auth_client.post(f"/api/v1/backups/{uploaded['id']}/restore")
    assert response.status_code == 400
    assert "bounce" in response.json()["detail"]
    assert "999" in response.json()["detail"]

async def test_should_restore_backup_when_file_is_valid(auth_client, backup_dir, db_session):
    uploaded = auth_client.post(
        "/api/v1/backups/upload", files=as_upload(make_backup_payload())
    ).json()

    response = auth_client.post(f"/api/v1/backups/{uploaded['id']}/restore")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Backup restored successfully"
    assert body["details"]["servers_restored"] == 1
    assert body["details"]["peers_restored"] == 1

    # Real rows were inserted, with the old server id remapped on the peer.
    from app.models.peer import Peer
    from app.models.server import Server

    server = (
        await db_session.execute(select(Server).where(Server.name == "restored-server"))
    ).scalar_one()
    peer = (
        await db_session.execute(select(Peer).where(Peer.name == "restored-peer"))
    ).scalar_one()
    assert server.interface == "wg9"
    assert peer.server_id == server.id

    assert "RESTORE" in await _audit_actions(db_session)


async def test_should_clear_existing_configuration_when_restoring_with_overwrite(
    auth_client, backup_dir, db_session, seeded_server_and_peer
):
    uploaded = auth_client.post(
        "/api/v1/backups/upload", files=as_upload(make_backup_payload())
    ).json()

    response = auth_client.post(
        f"/api/v1/backups/{uploaded['id']}/restore", params={"overwrite": "true"}
    )

    assert response.status_code == 200
    assert response.json()["details"]["cleared_existing"] is True

    from app.models.server import Server

    names = [
        row[0]
        for row in (await db_session.execute(select(Server.name))).all()
    ]
    # The pre-existing server was cleared and replaced by the backup content.
    assert names == ["restored-server"]


async def test_should_return_400_when_restoring_encrypted_backup_without_passphrase(
    auth_client, backup_dir, seeded_server_and_peer, db_session
):
    created = auth_client.post("/api/v1/backups/", json={}).json()
    import base64
    path = backup_dir / created["filename"]
    path.write_text(base64.b64encode(path.read_bytes()).decode())

    result = await db_session.execute(select(Backup).where(Backup.id == created["id"]))
    backup = result.scalar_one()
    backup.is_encrypted = True
    await db_session.commit()

    response = auth_client.post(f"/api/v1/backups/{created['id']}/restore")

    assert response.status_code == 400
    assert response.json()["detail"] == "Legacy unauthenticated backup requires explicit opt-in"


async def test_should_return_400_when_restore_file_is_missing(auth_client, backup_dir):
    created = auth_client.post("/api/v1/backups/", json={}).json()
    os.unlink(backup_dir / created["filename"])

    response = auth_client.post(f"/api/v1/backups/{created['id']}/restore")

    assert response.status_code == 400
    assert response.json()["detail"] == "Backup file not found"


async def test_should_return_400_when_restore_file_is_corrupt(auth_client, backup_dir):
    created = auth_client.post("/api/v1/backups/", json={}).json()
    (backup_dir / created["filename"]).write_text("{ definitely not json")

    response = auth_client.post(f"/api/v1/backups/{created['id']}/restore")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid backup format"


async def test_should_return_500_when_restore_document_is_structurally_invalid(
    auth_client, backup_dir
):
    payload = make_backup_payload()
    payload["servers"] = [{"not_a_server_field": True}]
    uploaded = auth_client.post(
        "/api/v1/backups/upload", files=as_upload(payload)
    ).json()

    response = auth_client.post(f"/api/v1/backups/{uploaded['id']}/restore")

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Failed to restore backup:")


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

async def test_should_delete_backup_row_and_file_when_it_exists(
    auth_client, backup_dir, db_session
):
    created = auth_client.post("/api/v1/backups/", json={"description": "bye"}).json()
    file_path = backup_dir / created["filename"]
    assert file_path.exists()

    response = auth_client.delete(f"/api/v1/backups/{created['id']}")

    assert response.status_code == 204
    assert not file_path.exists()
    result = await db_session.execute(select(Backup).where(Backup.id == created["id"]))
    assert result.scalar_one_or_none() is None
    assert "DELETE" in await _audit_actions(db_session)


async def test_should_still_delete_row_when_backup_file_cannot_be_removed(
    auth_client, backup_dir, db_session
):
    created = auth_client.post("/api/v1/backups/", json={}).json()
    # A read-only directory makes os.unlink fail while the row is still deleted.
    backup_dir.chmod(0o500)
    try:
        response = auth_client.delete(f"/api/v1/backups/{created['id']}")
        assert os.path.exists(backup_dir / created["filename"])
    finally:
        backup_dir.chmod(0o700)

    assert response.status_code == 204
    result = await db_session.execute(select(Backup).where(Backup.id == created["id"]))
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

async def test_should_return_empty_stats_when_no_backups(auth_client, backup_dir):
    response = auth_client.get("/api/v1/backups/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_backups"] == 0
    assert body["total_size"] == 0
    assert body["total_size_mb"] == 0.0
    assert body["encrypted_backups"] == 0
    assert body["latest_backup"] is None
    assert body["oldest_backup"] is None


async def test_should_summarise_backups_when_they_exist(
    auth_client, backup_dir, seeded_db, db_session
):
    # Record that encryption is deliberately unconfigured before seeding old metadata.
    assert auth_client.get("/api/v1/settings/backup-key").json() == {"configured": False}
    old = Backup(
        filename="old-backup.json",
        description="old",
        size_bytes=1024,
        is_encrypted=True,
        created_by_user_id=seeded_db["admin_id"],
        created_at=datetime.now(timezone.utc) - timedelta(days=7),
    )
    db_session.add(old)
    await db_session.commit()

    created = auth_client.post("/api/v1/backups/", json={"description": "new"}).json()

    response = auth_client.get("/api/v1/backups/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_backups"] == 2
    assert body["total_size_bytes"] == 1024 + created["file_size"]
    assert body["encrypted_backups"] == 1
    assert body["latest_backup"]["id"] == created["id"]
    assert body["latest_backup"]["description"] == "new"
    assert body["oldest_backup"]["id"] == old.id


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

async def test_should_require_authentication_when_listing_backups(api_client, seeded_db):
    response = api_client.get("/api/v1/backups/")

    assert response.status_code == 401
