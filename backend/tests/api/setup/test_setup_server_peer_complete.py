"""Tests for the server, peer and completion steps of the setup wizard."""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.main import app
from app.models.integration import Integration
from app.models.peer import Peer
from app.models.server import Server
from app.models.settings import GlobalSettings

DETECT_URL = "/api/v1/setup/detect-wireguard"
SERVER_URL = "/api/v1/setup/create-server"
PEER_URL = "/api/v1/setup/create-peer"
COMPLETE_URL = "/api/v1/setup/complete"

SERVER_PAYLOAD = {
    "name": "wg-main",
    "endpoint": "vpn.example.com",
    "listen_port": 51820,
    "ipv4_address": "10.0.0.1/24",
    "ipv6_address": "fd00::1/64",
    "dns": "1.1.1.1, 8.8.8.8",
}


async def _add_settings(session, **overrides):
    values = dict(
        secret_key="k" * 40,
        backup_dir="./backups",
        setup_completed=False,
        setup_current_step="server",
    )
    values.update(overrides)
    row = GlobalSettings(**values)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# /detect-wireguard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_report_binaries_when_wireguard_is_detected(api_client):
    with patch("app.api.setup.detect_wireguard_binaries", return_value={"wg": "/usr/bin/wg"}), \
         patch("app.api.setup.get_wireguard_paths", return_value={"wg": "/usr/bin/wg"}), \
         patch("app.api.setup.verify_wireguard_binary", return_value=True):
        response = api_client.get(DETECT_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    # wg-quick is not part of the detection result and must be reported as absent
    # instead of crashing the endpoint (regression guard).
    assert body["detected"] == {"wg": "/usr/bin/wg", "wg-quick": None}
    assert body["recommended"] == {"wg": "/usr/bin/wg", "wg-quick": "/usr/bin/wg-quick"}
    assert body["verified"] == {"wg": True, "wg-quick": False}
    assert body["message"] == "WireGuard binaries not detected, using default paths"


@pytest.mark.asyncio
async def test_should_report_both_binaries_when_wg_quick_is_also_detected(api_client):
    with patch(
        "app.api.setup.detect_wireguard_binaries",
        return_value={"wg": "/usr/bin/wg", "wg-quick": "/usr/bin/wg-quick"},
    ), patch(
        "app.api.setup.get_wireguard_paths",
        return_value={"wg": "/usr/bin/wg", "wg-quick": "/usr/bin/wg-quick"},
    ), patch("app.api.setup.verify_wireguard_binary", return_value=True):
        response = api_client.get(DETECT_URL)

    body = response.json()
    assert body["success"] is True
    assert body["verified"] == {"wg": True, "wg-quick": True}
    assert body["message"] == "WireGuard binaries detected"


@pytest.mark.asyncio
async def test_should_fall_back_to_defaults_when_detection_raises(api_client):
    with patch("app.api.setup.detect_wireguard_binaries", side_effect=OSError("no /usr/bin")):
        response = api_client.get(DETECT_URL)

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is False
    assert body["recommended"] == {"wg": "/usr/bin/wg", "wg-quick": "/usr/bin/wg-quick"}
    assert body["message"] == "Error detecting WireGuard binaries: no /usr/bin"


# ---------------------------------------------------------------------------
# /create-server
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_skip_server_creation_when_wireguard_is_missing(api_client, db_session, isolated_config):
    await _add_settings(db_session)

    with patch("app.api.setup.detect_wireguard_binaries", return_value={"wg": None}):
        response = api_client.post(SERVER_URL, json=SERVER_PAYLOAD)

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is False
    assert body["wireguard_missing"] is True
    assert "WireGuard is not installed" in body["message"]
    assert (await db_session.execute(select(Server))).scalars().all() == []

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.setup_current_step == "peer"


@pytest.mark.asyncio
async def test_should_create_server_with_keys_and_dns_when_wireguard_is_available(
    api_client, db_session, isolated_config
):
    await _add_settings(db_session)

    with patch("app.api.setup.detect_wireguard_binaries", return_value={"wg": "/usr/bin/wg"}):
        response = api_client.post(SERVER_URL, json=SERVER_PAYLOAD)

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["server_name"] == "wg-main"

    server = (await db_session.execute(select(Server))).scalars().one()
    assert server.id == body["server_id"]
    assert server.public_key == body["public_key"]
    assert server.interface == "wg0"
    assert server.endpoint == "vpn.example.com"
    assert server.listen_port == 51820
    assert server.ipv4_address == "10.0.0.1/24"
    assert server.ipv6_address == "fd00::1/64"
    assert server.dns_primary == "1.1.1.1"
    assert server.dns_secondary == "8.8.8.8"
    # Real WireGuard key material was generated for the server.
    assert server.private_key and server.private_key != server.public_key
    assert len(server.private_key) == 44

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.setup_current_step == "peer"


@pytest.mark.asyncio
async def test_should_leave_dns_empty_when_server_payload_has_no_dns(api_client, db_session, isolated_config):
    await _add_settings(db_session)
    payload = {k: v for k, v in SERVER_PAYLOAD.items() if k != "dns"}

    with patch("app.api.setup.detect_wireguard_binaries", return_value={"wg": "/usr/bin/wg"}):
        response = api_client.post(SERVER_URL, json=payload)

    assert response.status_code == 200
    server = (await db_session.execute(select(Server))).scalars().one()
    assert server.dns_primary is None
    assert server.dns_secondary is None


@pytest.mark.asyncio
async def test_should_reject_invalid_listen_port_when_creating_server(api_client):
    response = api_client.post(SERVER_URL, json={**SERVER_PAYLOAD, "listen_port": 80})

    assert response.status_code == 422
    assert response.json()["errors"]["body.listen_port"] == [
        "Listen port must be between 1024 and 65535"
    ]


@pytest.mark.asyncio
async def test_should_reject_invalid_endpoint_when_creating_server(api_client):
    response = api_client.post(SERVER_URL, json={**SERVER_PAYLOAD, "endpoint": "not a host!"})

    assert response.status_code == 422
    assert "body.endpoint" in response.json()["errors"]


# ---------------------------------------------------------------------------
# /create-peer
# ---------------------------------------------------------------------------

async def _add_user(session, username="firstadmin"):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("SuperSecret123"),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_server_row(session):
    server = Server(
        name="wg-main",
        interface="wg0",
        endpoint="vpn.example.com",
        listen_port=51820,
        private_key="cHJpdmF0ZWtleQ==",
        public_key="cHVibGlja2V5",
        ipv4_address="10.0.0.1/24",
        ipv6_address="fd00::1/64",
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


@pytest.mark.asyncio
async def test_should_skip_peer_creation_when_wireguard_is_missing(api_client, db_session, isolated_config):
    await _add_settings(db_session, setup_current_step="peer")

    with patch("app.api.setup.detect_wireguard_binaries", return_value={"wg": None}):
        response = api_client.post(PEER_URL, json={"server_id": 1, "name": "laptop"})

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is False
    assert body["wireguard_missing"] is True
    assert (await db_session.execute(select(Peer))).scalars().all() == []

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.setup_current_step == "complete"


@pytest.mark.asyncio
async def test_should_return_404_when_creating_peer_for_unknown_server(api_client, db_session, isolated_config):
    await _add_settings(db_session, setup_current_step="peer")

    with patch("app.api.setup.detect_wireguard_binaries", return_value={"wg": "/usr/bin/wg"}):
        response = api_client.post(PEER_URL, json={"server_id": 4242, "name": "laptop"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


@pytest.mark.asyncio
async def test_should_create_peer_with_explicit_ips_when_server_exists(api_client, db_session, isolated_config):
    await _add_settings(db_session, setup_current_step="peer")
    server = await _create_server_row(db_session)

    with patch("app.api.setup.detect_wireguard_binaries", return_value={"wg": "/usr/bin/wg"}):
        response = api_client.post(
            PEER_URL,
            json={
                "server_id": server.id,
                "name": "laptop",
                "ipv4_address": "10.0.0.2/32",
                "ipv6_address": "fd00::2/128",
                "dns": "9.9.9.9",
                "preshared_key": True,
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["peer_name"] == "laptop"
    assert body["ipv4_address"] == "10.0.0.2/32"
    assert body["ipv6_address"] == "fd00::2/128"

    peer = (await db_session.execute(select(Peer))).scalars().one()
    assert peer.id == body["peer_id"]
    assert peer.server_id == server.id
    assert peer.public_key == body["public_key"]
    assert peer.dns_primary == "9.9.9.9"
    assert peer.dns_secondary is None
    assert peer.preshared_key  # generated because preshared_key=True

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.setup_current_step == "complete"


@pytest.mark.asyncio
async def test_should_autofill_peer_addresses_when_none_provided(api_client, db_session, isolated_config):
    await _add_settings(db_session, setup_current_step="peer")
    server = await _create_server_row(db_session)

    with patch("app.api.setup.detect_wireguard_binaries", return_value={"wg": "/usr/bin/wg"}):
        response = api_client.post(PEER_URL, json={"server_id": server.id, "name": "phone"})

    body = response.json()
    assert response.status_code == 200
    assert body["ipv4_address"].startswith("10.0.0.")
    assert body["ipv6_address"].startswith("fd00:")

    peer = (await db_session.execute(select(Peer))).scalars().one()
    assert peer.preshared_key is None


# ---------------------------------------------------------------------------
# /complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_reject_complete_when_settings_missing(api_client, isolated_config):
    response = api_client.post(COMPLETE_URL)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Global settings not configured. Please configure settings first."
    )


@pytest.mark.asyncio
async def test_should_reject_complete_when_no_user_exists(api_client, db_session, isolated_config):
    await _add_settings(db_session, setup_current_step="complete")

    response = api_client.post(COMPLETE_URL)

    assert response.status_code == 400
    assert response.json()["detail"] == "No admin user created. Please initialize setup first."


class _FakeBackup:
    def __init__(self, backup_id=7, error=None):
        self.backup_id = backup_id
        self.error = error
        self.calls = []

    async def create_backup(self, db, description, user_id):
        self.calls.append({"description": description, "user_id": user_id})
        if self.error:
            raise self.error

        class _Backup:
            id = self.backup_id

        return _Backup


@pytest.mark.asyncio
async def test_should_complete_setup_and_create_backup_and_integration(api_client, db_session, isolated_config):
    admin = await _add_user(db_session)
    await _add_settings(db_session, setup_current_step="complete")
    fake_backup = _FakeBackup()

    with app.container.backup_service.override(fake_backup):
        response = api_client.post(COMPLETE_URL)

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Setup completed successfully",
        "backup_id": 7,
    }
    assert fake_backup.calls[0]["description"] == "Initial setup backup - auto-generated"
    assert fake_backup.calls[0]["user_id"] == admin.id

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.setup_completed is True
    assert settings.setup_current_step is None

    integrations = (await db_session.execute(select(Integration))).scalars().all()
    assert [i.name for i in integrations] == ["In-App Notifications"]
    assert integrations[0].type == "notification"
    assert integrations[0].enabled is True

    status = api_client.get("/api/v1/setup/status")
    assert status.json()["setup_completed"] is True


@pytest.mark.asyncio
async def test_should_still_complete_when_backup_creation_fails(api_client, db_session, isolated_config):
    await _add_user(db_session)
    await _add_settings(db_session, setup_current_step="complete")
    fake_backup = _FakeBackup(error=RuntimeError("disk full"))

    with app.container.backup_service.override(fake_backup):
        response = api_client.post(COMPLETE_URL)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["backup_id"] is None

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.setup_completed is True


@pytest.mark.asyncio
async def test_should_still_complete_when_integration_creation_fails(
    api_client, db_session, isolated_config
):
    class ExplodingIntegrationService:
        async def create_integration(self, **kwargs):
            raise RuntimeError("integrations table is locked")

    await _add_user(db_session)
    await _add_settings(db_session, setup_current_step="complete")

    with app.container.backup_service.override(_FakeBackup()), \
         app.container.integration_service.override(ExplodingIntegrationService()):
        response = api_client.post(COMPLETE_URL)

    assert response.status_code == 200
    assert response.json()["backup_id"] == 7
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.setup_completed is True


@pytest.mark.asyncio
async def test_should_not_duplicate_integration_when_completing_twice(api_client, db_session, isolated_config):
    await _add_user(db_session)
    await _add_settings(db_session, setup_current_step="complete", setup_completed=True)
    db_session.add(
        Integration(
            name="In-App Notifications",
            type="notification",
            config={},
            events_subscribed=[],
            enabled=True,
        )
    )
    await db_session.commit()

    with app.container.backup_service.override(_FakeBackup()):
        response = api_client.post(COMPLETE_URL)

    assert response.status_code == 200
    integrations = (await db_session.execute(select(Integration))).scalars().all()
    assert len(integrations) == 1
