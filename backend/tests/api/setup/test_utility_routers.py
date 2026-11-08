"""Tests for the small utility routers: system, utils, version, notifications."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.notification import Notification

SYSTEM_URL = "/api/v1/system"
UTILS_URL = "/api/v1/utils"
VERSION_URL = "/api/v1/version"
NOTIFICATIONS_URL = "/api/v1/notifications"


# ---------------------------------------------------------------------------
# /system
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_return_runtime_and_host_info_when_admin_requests_system(auth_client):
    response = auth_client.get(SYSTEM_URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"app", "host"}
    assert body["app"]["name"]
    assert body["app"]["version"]
    assert body["app"]["repository"].startswith("https://")
    assert body["app"]["python_version"].startswith("3.")
    assert body["app"]["uptime_seconds"] >= 0
    assert body["host"]["hostname"]
    assert body["host"]["cpu_count"] >= 1
    assert body["host"]["ram_total_bytes"] > 0
    assert 0 <= body["host"]["ram_percent"] <= 100


@pytest.mark.asyncio
async def test_should_deny_system_info_when_requester_is_standard_user(user_client):
    response = user_client.get(SYSTEM_URL)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_should_deny_system_info_when_unauthenticated(api_client, seeded_db):
    assert api_client.get(SYSTEM_URL).status_code == 401


# ---------------------------------------------------------------------------
# /utils
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_generate_wireguard_keypair_when_requested(auth_client):
    response = auth_client.get(f"{UTILS_URL}/generate-keypair")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"private_key", "public_key"}
    assert len(body["private_key"]) == 44
    assert len(body["public_key"]) == 44
    assert body["private_key"] != body["public_key"]


@pytest.mark.asyncio
async def test_should_generate_preshared_key_when_requested(auth_client):
    response = auth_client.get(f"{UTILS_URL}/generate-preshared-key")

    assert response.status_code == 200
    assert len(response.json()["preshared_key"]) == 44


@pytest.mark.asyncio
async def test_should_derive_public_key_when_private_key_is_valid(auth_client):
    keypair = auth_client.get(f"{UTILS_URL}/generate-keypair").json()

    response = auth_client.post(
        f"{UTILS_URL}/derive-public-key", json={"private_key": keypair["private_key"]}
    )

    assert response.status_code == 200
    assert response.json()["public_key"] == keypair["public_key"]


@pytest.mark.asyncio
async def test_should_return_400_when_private_key_is_invalid(auth_client):
    response = auth_client.post(
        f"{UTILS_URL}/derive-public-key", json={"private_key": "not-a-wireguard-key"}
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Failed to derive public key:")


@pytest.mark.asyncio
async def test_should_deny_key_generation_when_requester_is_standard_user(user_client):
    assert user_client.get(f"{UTILS_URL}/generate-keypair").status_code == 403


# ---------------------------------------------------------------------------
# /version
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_return_current_version_when_requested(auth_client):
    response = auth_client.get(f"{VERSION_URL}/current")

    assert response.status_code == 200
    body = response.json()
    assert {"version", "name", "repository"} <= set(body)
    assert body["version"].count(".") >= 1


@pytest.mark.asyncio
async def test_should_return_changelog_when_requested(auth_client):
    response = auth_client.get(f"{VERSION_URL}/changelog")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_should_delegate_update_check_to_service_when_requested(auth_client):
    payload = {
        "current_version": "1.0.0",
        "latest_version": "1.1.0",
        "update_available": True,
        "release_url": "https://github.com/example/linguard/releases/tag/v1.1.0",
        "release_notes": "- faster",
        "published_at": "2026-01-01T00:00:00Z",
        "release_name": "v1.1.0",
    }
    with patch(
        "app.services.version_service.VersionService.check_for_updates",
        AsyncMock(return_value=payload),
    ):
        response = auth_client.get(f"{VERSION_URL}/check-updates")

    assert response.status_code == 200
    assert response.json() == payload


@pytest.mark.asyncio
async def test_should_deny_version_endpoints_when_requester_is_standard_user(user_client):
    assert user_client.get(f"{VERSION_URL}/current").status_code == 403


# ---------------------------------------------------------------------------
# /notifications
# ---------------------------------------------------------------------------

async def _add_notification(session, user_id, title="Ping", read=False):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=f"{title} body",
        type="info",
        event_type="peer.connected",
        source_type="peer",
        source_id=3,
        read=read,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


@pytest.mark.asyncio
async def test_should_create_notification_when_admin_posts_one(auth_client, db_session, seeded_db):
    response = auth_client.post(
        NOTIFICATIONS_URL + "/",
        json={
            "user_id": seeded_db["user_id"],
            "title": "Welcome",
            "message": "Hello bob",
            "type": "info",
            "link": "/servers",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Welcome"
    assert body["read"] is False

    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert [n.id for n in rows] == [body["id"]]
    assert rows[0].user_id == seeded_db["user_id"]


@pytest.mark.asyncio
async def test_should_list_only_own_notifications_when_user_requests_them(auth_client, db_session, seeded_db):
    await _add_notification(db_session, seeded_db["admin_id"], "Mine")
    await _add_notification(db_session, seeded_db["user_id"], "Bobs")

    response = auth_client.get(NOTIFICATIONS_URL + "/")

    assert response.status_code == 200
    titles = [n["title"] for n in response.json()]
    assert titles == ["Mine"]


@pytest.mark.asyncio
async def test_should_filter_unread_notifications_when_unread_only_requested(auth_client, db_session, seeded_db):
    await _add_notification(db_session, seeded_db["admin_id"], "Unread")
    await _add_notification(db_session, seeded_db["admin_id"], "Read", read=True)

    response = auth_client.get(NOTIFICATIONS_URL + "/", params={"unread_only": True})

    assert [n["title"] for n in response.json()] == ["Unread"]


@pytest.mark.asyncio
async def test_should_limit_notifications_when_limit_and_offset_given(auth_client, db_session, seeded_db):
    for i in range(3):
        await _add_notification(db_session, seeded_db["admin_id"], f"N{i}")

    first = auth_client.get(NOTIFICATIONS_URL + "/", params={"limit": 1, "offset": 0})
    second = auth_client.get(NOTIFICATIONS_URL + "/", params={"limit": 1, "offset": 1})

    assert len(first.json()) == 1
    assert first.json()[0]["id"] != second.json()[0]["id"]


@pytest.mark.asyncio
async def test_should_count_unread_notifications_when_requested(auth_client, db_session, seeded_db):
    await _add_notification(db_session, seeded_db["admin_id"], "Unread")
    await _add_notification(db_session, seeded_db["admin_id"], "Read", read=True)

    response = auth_client.get(f"{NOTIFICATIONS_URL}/unread/count")

    assert response.status_code == 200
    assert response.json() == {"count": 1}


@pytest.mark.asyncio
async def test_should_mark_notification_read_when_user_puts_it(auth_client, db_session, seeded_db):
    notification = await _add_notification(db_session, seeded_db["admin_id"])

    response = auth_client.put(
        f"{NOTIFICATIONS_URL}/{notification.id}", json={"read": True}
    )

    assert response.status_code == 200
    assert response.json()["read"] is True
    refreshed = (
        await db_session.execute(select(Notification).where(Notification.id == notification.id))
    ).scalars().one()
    await db_session.refresh(refreshed)
    assert refreshed.read is True
    assert refreshed.read_at is not None


@pytest.mark.asyncio
async def test_should_return_404_when_marking_missing_notification_read(auth_client):
    response = auth_client.put(f"{NOTIFICATIONS_URL}/9999", json={"read": True})

    assert response.status_code == 404
    assert response.json()["detail"] == "Notification not found"


@pytest.mark.asyncio
async def test_should_mark_all_notifications_read_when_requested(auth_client, db_session, seeded_db):
    await _add_notification(db_session, seeded_db["admin_id"], "A")
    await _add_notification(db_session, seeded_db["admin_id"], "B")

    response = auth_client.put(f"{NOTIFICATIONS_URL}/read/all")

    assert response.status_code == 200
    assert response.json() == {"marked_read": 2}
    assert auth_client.get(f"{NOTIFICATIONS_URL}/unread/count").json() == {"count": 0}


@pytest.mark.asyncio
async def test_should_delete_notification_when_user_deletes_it(auth_client, db_session, seeded_db):
    notification = await _add_notification(db_session, seeded_db["admin_id"])

    response = auth_client.delete(f"{NOTIFICATIONS_URL}/{notification.id}")

    assert response.status_code == 204
    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_should_return_404_when_deleting_missing_notification(auth_client):
    response = auth_client.delete(f"{NOTIFICATIONS_URL}/9999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_should_delete_all_notifications_when_requested(auth_client, db_session, seeded_db):
    await _add_notification(db_session, seeded_db["admin_id"], "A")
    await _add_notification(db_session, seeded_db["user_id"], "Bobs")

    response = auth_client.delete(f"{NOTIFICATIONS_URL}/all")

    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
    # Other users' notifications are untouched.
    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert [n.title for n in rows] == ["Bobs"]


@pytest.mark.asyncio
async def test_should_deny_notifications_when_unauthenticated(api_client, seeded_db):
    assert api_client.get(NOTIFICATIONS_URL + "/").status_code == 401
