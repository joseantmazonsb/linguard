"""Tests for ``app/api/import_config.py``.

Uploads are real multipart files, parsing uses the production ``ConfigParser``
and imported rows are written to the per-test SQLite database.
"""

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.peer import Peer
from app.models.server import Server

BASE = "/api/v1/import"

SERVER_CONFIG = """\
[Interface]
PrivateKey = server-private-key
Address = 10.10.0.1/24, fd00::1/64
ListenPort = 51820
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = peer-public-key
PresharedKey = peer-preshared-key
AllowedIPs = 10.10.0.2/32, fd00::2/128
PersistentKeepalive = 25
"""

CLIENT_CONFIG = """\
[Interface]
PrivateKey = client-private-key
Address = 10.10.0.2/32, fd00::2/128
DNS = 9.9.9.9

[Peer]
PublicKey = server-public-key
Endpoint = vpn.example.com:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 15
"""


def _upload(content, filename="wg0.conf"):
    body = content.encode() if isinstance(content, str) else content
    return {"file": (filename, body, "text/plain")}


# ---------------------------------------------------------------------------
# /parse
# ---------------------------------------------------------------------------

async def test_should_parse_server_config_when_file_has_listen_port(auth_client):
    response = auth_client.post(f"{BASE}/parse", files=_upload(SERVER_CONFIG))

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "server"
    server = body["parsed_data"]["server"]
    assert server["private_key"] == "server-private-key"
    assert server["listen_port"] == 51820
    assert server["ipv4_address"] == "10.10.0.1/24"
    assert server["ipv6_address"] == "fd00::1/64"
    assert server["dns_primary"] == "1.1.1.1"
    assert server["dns_secondary"] == "8.8.8.8"

    peer = body["parsed_data"]["peers"][0]
    assert peer["public_key"] == "peer-public-key"
    assert peer["preshared_key"] == "peer-preshared-key"
    assert peer["ipv4_allowed_ips"] == "10.10.0.2/32"
    assert peer["ipv6_allowed_ips"] == "fd00::2/128"
    assert peer["persistent_keepalive"] == 25

    assert body["missing_fields"]["server"] == ["name", "interface", "endpoint", "description"]
    assert body["missing_fields"]["peers"] == [
        {
            "public_key": "peer-public-key",
            "missing": ["name", "description", "email"],
        }
    ]


async def test_should_parse_client_config_when_file_has_endpoint(auth_client):
    response = auth_client.post(f"{BASE}/parse", files=_upload(CLIENT_CONFIG))

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "client"
    data = body["parsed_data"]
    assert data["private_key"] == "client-private-key"
    assert data["ipv4_address"] == "10.10.0.2/32"
    assert data["ipv6_address"] == "fd00::2/128"
    assert data["dns_primary"] == "9.9.9.9"
    assert data["server_public_key"] == "server-public-key"
    assert data["server_endpoint"] == "vpn.example.com"
    assert data["server_port"] == 51820
    assert data["ipv4_allowed_ips"] == "0.0.0.0/0"
    assert data["ipv6_allowed_ips"] == "::/0"
    assert data["persistent_keepalive"] == 15
    assert body["missing_fields"] == ["name", "server_id", "description", "email"]


async def test_should_treat_config_as_server_when_it_has_no_endpoint(auth_client):
    config = """\
[Interface]
PrivateKey = lonely-key
ListenPort = 51900
"""

    response = auth_client.post(f"{BASE}/parse", files=_upload(config))

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "server"
    assert body["parsed_data"]["server"]["listen_port"] == 51900


async def test_should_reject_parse_when_file_is_not_utf8(auth_client):
    response = auth_client.post(f"{BASE}/parse", files=_upload(b"\xff\xfe\x00\x00binary"))

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file encoding. Expected UTF-8."


# ---------------------------------------------------------------------------
# /server
# ---------------------------------------------------------------------------

async def test_should_import_server_when_payload_is_complete(auth_client, db_session):
    payload = {
        "parsed_data": {
            "private_key": "imported-private-key",
            "public_key": "imported-public-key",
            "listen_port": 51830,
            "ipv4_address": "10.20.0.1/24",
            "dns_primary": "1.1.1.1",
        },
        "additional_data": {
            "name": "imported-server",
            "interface": "wg7",
            "endpoint": "vpn.imported.example",
            "description": "imported from file",
        },
    }

    response = auth_client.post(f"{BASE}/server", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "imported-server"
    assert body["interface"] == "wg7"
    assert body["public_key"] == "imported-public-key"
    assert body["endpoint"] == "vpn.imported.example"
    assert body["peer_count"] == 0

    stored = (
        await db_session.execute(select(Server).where(Server.id == body["id"]))
    ).scalar_one()
    assert stored.private_key == "imported-private-key"
    assert stored.listen_port == 51830
    assert stored.ipv4_address == "10.20.0.1/24"

    actions = [row[0] for row in (await db_session.execute(select(AuditLog.action))).all()]
    assert actions == ["import_server"]


async def test_should_generate_keypair_when_imported_server_has_no_public_key(
    auth_client, db_session
):
    payload = {
        "parsed_data": {
            "private_key": "only-private-key",
            "listen_port": 51831,
            "ipv4_address": "10.30.0.1/24",
        },
        "additional_data": {"name": "generated-key-server", "interface": "wg8"},
    }

    response = auth_client.post(f"{BASE}/server", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["public_key"]
    assert body["public_key"] != "only-private-key"

    stored = (
        await db_session.execute(select(Server).where(Server.id == body["id"]))
    ).scalar_one()
    assert stored.public_key == body["public_key"]
    assert stored.private_key != "only-private-key"  # replaced by the fresh keypair


async def test_should_reject_server_import_when_required_fields_are_missing(auth_client):
    base = {"parsed_data": {"private_key": "k", "public_key": "p"}}

    no_name = auth_client.post(
        f"{BASE}/server", json={**base, "additional_data": {"interface": "wg9"}}
    )
    assert no_name.status_code == 400
    assert no_name.json()["detail"] == "Server name is required"

    no_interface = auth_client.post(
        f"{BASE}/server", json={**base, "additional_data": {"name": "srv"}}
    )
    assert no_interface.status_code == 400
    assert no_interface.json()["detail"] == "Interface name is required"

    no_key = auth_client.post(
        f"{BASE}/server",
        json={
            "parsed_data": {"public_key": "p"},
            "additional_data": {"name": "srv", "interface": "wg9"},
        },
    )
    assert no_key.status_code == 400
    assert no_key.json()["detail"] == "Private key not found in config"


# ---------------------------------------------------------------------------
# /peer
# ---------------------------------------------------------------------------

async def test_should_import_peer_when_payload_is_complete(auth_client, db_session, server):
    payload = {
        "parsed_data": {
            "private_key": "imported-peer-private",
            "public_key": "imported-peer-public",
            "ipv4_address": "10.0.0.9/32",
            "ipv4_allowed_ips": "0.0.0.0/0",
            "persistent_keepalive": 30,
            "preshared_key": "peer-psk",
        },
        "additional_data": {
            "name": "imported-peer",
            "server_id": server.id,
            "description": "from client config",
            "email": "peer@example.com",
        },
    }

    response = auth_client.post(f"{BASE}/peer", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "imported-peer"
    assert body["server_id"] == server.id
    assert body["public_key"] == "imported-peer-public"
    assert body["allowed_ips"] == "0.0.0.0/0"
    assert body["enabled"] is True

    stored = (
        await db_session.execute(select(Peer).where(Peer.id == body["id"]))
    ).scalar_one()
    assert stored.private_key == "imported-peer-private"
    assert stored.preshared_key == "peer-psk"
    assert stored.persistent_keepalive == 30
    assert stored.email == "peer@example.com"

    actions = [row[0] for row in (await db_session.execute(select(AuditLog.action))).all()]
    assert actions == ["import_peer"]


async def test_should_generate_keypair_when_imported_peer_has_no_public_key(
    auth_client, db_session, server
):
    payload = {
        "parsed_data": {"private_key": "peer-private-only", "ipv4_address": "10.0.0.10/32"},
        "additional_data": {"name": "generated-peer", "server_id": server.id},
    }

    response = auth_client.post(f"{BASE}/peer", json=payload)

    assert response.status_code == 200
    body = response.json()
    stored = (
        await db_session.execute(select(Peer).where(Peer.id == body["id"]))
    ).scalar_one()
    assert stored.public_key == body["public_key"]
    assert stored.public_key != "peer-private-only"
    assert stored.persistent_keepalive == 25  # default


async def test_should_reject_peer_import_when_required_fields_are_missing(
    auth_client, server
):
    base = {"parsed_data": {"private_key": "k", "public_key": "p"}}

    no_name = auth_client.post(
        f"{BASE}/peer", json={**base, "additional_data": {"server_id": server.id}}
    )
    assert no_name.status_code == 400
    assert no_name.json()["detail"] == "Peer name is required"

    no_server = auth_client.post(
        f"{BASE}/peer", json={**base, "additional_data": {"name": "peer"}}
    )
    assert no_server.status_code == 400
    assert no_server.json()["detail"] == "server_id is required"

    no_key = auth_client.post(
        f"{BASE}/peer",
        json={
            "parsed_data": {"public_key": "p"},
            "additional_data": {"name": "peer", "server_id": server.id},
        },
    )
    assert no_key.status_code == 400
    assert no_key.json()["detail"] == "Private key not found in config"


async def test_should_return_404_when_importing_peer_for_unknown_server(auth_client):
    response = auth_client.post(
        f"{BASE}/peer",
        json={
            "parsed_data": {"private_key": "k", "public_key": "p"},
            "additional_data": {"name": "peer", "server_id": 4242},
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_require_authentication_when_parsing_config(api_client, seeded_db):
    response = api_client.post(f"{BASE}/parse", files=_upload(SERVER_CONFIG))

    assert response.status_code == 401
