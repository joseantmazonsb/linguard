"""Payload builders shared by the backup API tests."""

import json


def make_backup_payload(server_name="restored-server", peer_name="restored-peer"):
    """Build a valid Linguard backup document (same shape the service writes)."""
    return {
        "version": "1.0",
        "timestamp": "2026-01-01T00:00:00",
        "global_settings": {"dns_primary": "1.1.1.1", "dns_secondary": "8.8.8.8"},
        "servers": [
            {
                "id": 900,
                "name": server_name,
                "interface": "wg9",
                "description": "restored from upload",
                "public_key": "restored-server-public-key",
                "private_key": "restored-server-private-key",
                "endpoint": "restored.example.com",
                "listen_port": 51900,
                "ipv4_address": "10.90.0.1/24",
                "ipv6_address": None,
                "dns_primary": None,
                "dns_secondary": None,
                "is_bounce_server": False,
                "bounce_via_server_id": None,
                "enabled": True,
            }
        ],
        "peers": [
            {
                "id": 901,
                "server_id": 900,
                "name": peer_name,
                "description": None,
                "email": None,
                "public_key": "restored-peer-public-key",
                "private_key": "restored-peer-private-key",
                "preshared_key": None,
                "ipv4_address": "10.90.0.2",
                "ipv6_address": None,
                "ipv4_allowed_ips": None,
                "ipv6_allowed_ips": None,
                "dns_primary": None,
                "dns_secondary": None,
                "persistent_keepalive": 25,
                "endpoint": None,
                "enabled": True,
            }
        ],
        "integrations": [],
        "traffic_triggers": [],
        "plugins": [],
    }


def as_upload(payload, filename="backup.json"):
    """Wrap a payload (dict or raw string) as a multipart upload tuple."""
    body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
    if isinstance(body, str):
        body = body.encode()
    return {"file": (filename, body, "application/json")}
