"""Tests for NotificationService: persistence, read state, and event-driven notifications."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.integration import Integration
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import NotificationService


@pytest.fixture
def service():
    return NotificationService()


@pytest.fixture(autouse=True)
def no_ws_broadcast():
    """WebSocket broadcast is an external boundary; capture it for assertions."""
    with patch("app.api.ws.broadcast_notification", new=AsyncMock()) as broadcast:
        yield broadcast


async def _seed_notification(db_session, user_id, title, read=False, created_at=None, **kwargs):
    notification = Notification(
        user_id=user_id, title=title, message=f"message for {title}", type=kwargs.pop("type", "info"),
        read=read, created_at=created_at or datetime.utcnow(), **kwargs
    )
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)
    return notification


# ----------------------------------------------------------------------------
# create_notification
# ----------------------------------------------------------------------------


async def test_should_persist_notification_when_created(service, seeded_db, db_session, no_ws_broadcast):
    notification = await service.create_notification(
        db_session,
        user_id=seeded_db["admin_id"],
        title="Hello",
        message="World",
        type="warning",
        link="/servers",
        event_type="server.created",
        source_type="server",
        source_id=7,
    )

    assert notification.id is not None
    stored = (await db_session.execute(
        select(Notification).where(Notification.id == notification.id)
    )).scalar_one()
    assert stored.title == "Hello"
    assert stored.message == "World"
    assert stored.type == "warning"
    assert stored.link == "/servers"
    assert stored.event_type == "server.created"
    assert stored.source_type == "server"
    assert stored.source_id == 7
    assert stored.read is False

    no_ws_broadcast.assert_awaited_once()
    payload = no_ws_broadcast.await_args.args[0]
    assert payload["id"] == notification.id
    assert payload["title"] == "Hello"
    assert payload["type"] == "warning"
    assert payload["link"] == "/servers"
    assert payload["read"] is False
    assert payload["created_at"] is not None


async def test_should_flush_without_committing_when_auto_commit_disabled(
    service, seeded_db, api_db, db_session, no_ws_broadcast
):
    notification = await service.create_notification(
        db_session,
        user_id=seeded_db["admin_id"],
        title="Pending",
        message="Not committed yet",
        auto_commit=False,
    )

    assert notification.id is not None
    no_ws_broadcast.assert_awaited_once()

    # The row was only flushed: rolling back discards it, proving there was no commit.
    await db_session.rollback()
    visible = (await db_session.execute(select(Notification))).scalars().all()
    assert visible == []


async def test_should_still_create_notification_when_broadcast_fails(service, seeded_db, db_session):
    with patch("app.api.ws.broadcast_notification", AsyncMock(side_effect=RuntimeError("no clients"))):
        notification = await service.create_notification(
            db_session, user_id=seeded_db["admin_id"], title="T", message="M"
        )

    assert notification.id is not None


# ----------------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------------


async def test_should_return_notifications_newest_first_when_listing(service, seeded_db, db_session):
    now = datetime.utcnow()
    old = await _seed_notification(db_session, seeded_db["admin_id"], "old", created_at=now - timedelta(minutes=5))
    new = await _seed_notification(db_session, seeded_db["admin_id"], "new", created_at=now)
    await _seed_notification(db_session, seeded_db["user_id"], "other-user", created_at=now)

    result = await service.get_user_notifications(db_session, seeded_db["admin_id"])

    assert [n.id for n in result] == [new.id, old.id]


async def test_should_only_return_unread_when_unread_filter_used(service, seeded_db, db_session):
    read = await _seed_notification(db_session, seeded_db["admin_id"], "read", read=True)
    unread = await _seed_notification(db_session, seeded_db["admin_id"], "unread")

    result = await service.get_user_notifications(db_session, seeded_db["admin_id"], unread_only=True)

    assert [n.id for n in result] == [unread.id]
    assert read.id not in [n.id for n in result]


async def test_should_apply_limit_and_offset_when_listing(service, seeded_db, db_session):
    now = datetime.utcnow()
    created = [
        await _seed_notification(
            db_session, seeded_db["admin_id"], f"n{i}", created_at=now - timedelta(minutes=i)
        )
        for i in range(3)
    ]

    page = await service.get_user_notifications(db_session, seeded_db["admin_id"], limit=1, offset=1)

    assert [n.id for n in page] == [created[1].id]


async def test_should_count_unread_notifications_when_requested(service, seeded_db, db_session):
    await _seed_notification(db_session, seeded_db["admin_id"], "a")
    await _seed_notification(db_session, seeded_db["admin_id"], "b")
    await _seed_notification(db_session, seeded_db["admin_id"], "c", read=True)

    assert await service.get_unread_count(db_session, seeded_db["admin_id"]) == 2


# ----------------------------------------------------------------------------
# Read state
# ----------------------------------------------------------------------------


async def test_should_mark_notification_read_when_owner_requests_it(service, seeded_db, db_session):
    notification = await _seed_notification(db_session, seeded_db["admin_id"], "a")

    updated = await service.mark_as_read(db_session, notification.id, seeded_db["admin_id"])

    assert updated.read is True
    assert updated.read_at is not None


async def test_should_leave_read_at_untouched_when_notification_already_read(service, seeded_db, db_session):
    notification = await _seed_notification(db_session, seeded_db["admin_id"], "a", read=True)
    original = notification.read_at

    updated = await service.mark_as_read(db_session, notification.id, seeded_db["admin_id"])

    assert updated.read is True
    assert updated.read_at == original


async def test_should_return_none_when_marking_unknown_notification_read(service, seeded_db, db_session):
    assert await service.mark_as_read(db_session, 9999, seeded_db["admin_id"]) is None


async def test_should_not_mark_notification_read_when_owned_by_another_user(service, seeded_db, db_session):
    notification = await _seed_notification(db_session, seeded_db["user_id"], "a")

    result = await service.mark_as_read(db_session, notification.id, seeded_db["admin_id"])

    assert result is None
    await db_session.refresh(notification)
    assert notification.read is False


async def test_should_mark_all_unread_notifications_read_when_requested(service, seeded_db, db_session):
    await _seed_notification(db_session, seeded_db["admin_id"], "a")
    await _seed_notification(db_session, seeded_db["admin_id"], "b")
    already = await _seed_notification(db_session, seeded_db["admin_id"], "c", read=True)
    other = await _seed_notification(db_session, seeded_db["user_id"], "d")

    count = await service.mark_all_as_read(db_session, seeded_db["admin_id"])

    assert count == 2
    await db_session.refresh(other)
    assert other.read is False
    assert already.read is True


# ----------------------------------------------------------------------------
# Deletion
# ----------------------------------------------------------------------------


async def test_should_delete_notification_when_owner_requests_it(service, seeded_db, db_session):
    notification = await _seed_notification(db_session, seeded_db["admin_id"], "a")

    assert await service.delete_notification(db_session, notification.id, seeded_db["admin_id"]) is True
    assert (await db_session.execute(select(Notification))).scalars().all() == []


async def test_should_not_delete_notification_when_owned_by_another_user(service, seeded_db, db_session):
    notification = await _seed_notification(db_session, seeded_db["user_id"], "a")

    assert await service.delete_notification(db_session, notification.id, seeded_db["admin_id"]) is False
    assert len((await db_session.execute(select(Notification))).scalars().all()) == 1


async def test_should_return_false_when_deleting_unknown_notification(service, seeded_db, db_session):
    assert await service.delete_notification(db_session, 1234, seeded_db["admin_id"]) is False


async def test_should_delete_only_own_notifications_when_deleting_all(service, seeded_db, db_session):
    await _seed_notification(db_session, seeded_db["admin_id"], "a")
    await _seed_notification(db_session, seeded_db["admin_id"], "b")
    other = await _seed_notification(db_session, seeded_db["user_id"], "c")

    count = await service.delete_all_notifications(db_session, seeded_db["admin_id"])

    assert count == 2
    remaining = (await db_session.execute(select(Notification))).scalars().all()
    assert [n.id for n in remaining] == [other.id]


# ----------------------------------------------------------------------------
# notify_from_integration
# ----------------------------------------------------------------------------


async def _integration(db_session):
    integration = Integration(
        name="In-App Notifications",
        type="notification",
        config={},
        events_subscribed=["server.created"],
        enabled=True,
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)
    return integration


async def test_should_notify_every_user_when_integration_event_fires(service, seeded_db, db_session):
    integration = await _integration(db_session)

    await service.notify_from_integration(db_session, integration, {
        "event_type": "server.created",
        "resource_type": "server",
        "resource_id": 3,
        "metadata": {"name": "edge-1"},
        "timestamp": "2026-01-01 00:00:00 UTC",
    })

    notifications = (await db_session.execute(select(Notification))).scalars().all()
    users = (await db_session.execute(select(User))).scalars().all()
    assert {n.user_id for n in notifications} == {u.id for u in users}
    for n in notifications:
        assert n.title == "New Server Created"
        assert n.message == "Server 'edge-1' has been created and is ready to use."
        assert n.link == "/servers"
        assert n.type == "event"
        assert n.event_type == "server.created"
        assert n.source_type == "server"
        assert n.source_id == 3


async def test_should_use_resource_id_when_event_payload_has_no_name(service, seeded_db, db_session):
    integration = await _integration(db_session)

    await service.notify_from_integration(db_session, integration, {
        "event_type": "peer.deleted",
        "resource_type": "peer",
        "resource_id": 11,
        "metadata": {},
    })

    notification = (await db_session.execute(select(Notification))).scalars().first()
    assert notification.message == "Peer 'peer #11' has been removed from the network."


async def test_should_accept_legacy_event_format_when_dispatching(service, seeded_db, db_session):
    integration = await _integration(db_session)

    await service.notify_from_integration(db_session, integration, {
        "event_type": "peer.connected",
        "source_type": "peer",
        "source_id": 5,
        "payload": {"name": "laptop"},
    })

    notification = (await db_session.execute(select(Notification))).scalars().first()
    assert notification.title == "Peer Connected"
    assert notification.source_type == "peer"
    assert notification.source_id == 5


@pytest.mark.parametrize(
    "event_type, source_type, source_id, payload, expected",
    [
        ("global.traffic_threshold_exceeded", "global", None, {"current_bytes": 1234},
         ("Traffic Alert", "Global traffic threshold has been exceeded. Current: 1234 bytes.", "/traffic-triggers")),
        ("traffic.threshold_exceeded", "server", 2,
         {"name": "wg0", "current_bytes": 99, "exceeded_by_percent": 10, "trigger_id": 8},
         ("Traffic Alert", "Traffic threshold exceeded: wg0. Current: 99 bytes, exceeded by 10%.",
          "/traffic-triggers?trigger=8")),
        ("server.traffic_threshold_exceeded", "server", 2, {"name": "wg0"},
         ("Traffic Alert", "Server 'wg0' has exceeded its traffic threshold.", "/servers")),
        ("backup.created", "backup", 4, {},
         ("Backup Created", "New system backup has been created successfully.", "/backup")),
        ("backup.restored", "backup", 4, {},
         ("Backup Restored", "System has been restored from backup successfully.", "/backup")),
        ("backup.deleted", "backup", 4, {},
         ("Backup Deleted", "Backup has been permanently deleted.", "/backup")),
        ("integration.triggered", "integration", 1, {},
         ("Integration Triggered", "An integration has been triggered by a system event.", "/integrations")),
        ("settings.updated", "settings", 1, {},
         ("Settings Updated", "System settings have been updated successfully.", "/settings")),
        ("user.login", "user", 1, {}, ("User Login", "User logged in to the system.", None)),
        ("user.logout", "user", 1, {}, ("User Logout", "User logged out from the system.", None)),
        ("user.updated", "user", 1, {}, ("Profile Updated", "User profile has been updated.", None)),
        ("peer.migrated", "peer", 3, {"name": "phone"},
         ("Peer Migrated", "Peer 'phone' has been migrated to a different server.", "/peers")),
        ("peer.edited", "peer", 3, {"name": "phone"},
         ("Peer Updated", "Peer 'phone' configuration has been updated.", "/peers")),
        ("peer.disconnected", "peer", 3, {"name": "phone"},
         ("Peer Disconnected", "Peer 'phone' has disconnected from the VPN.", "/peers")),
        ("peer.traffic_threshold_exceeded", "peer", 3, {"name": "phone"},
         ("Traffic Alert", "Peer 'phone' has exceeded its traffic threshold.", "/peers")),
        ("server.edited", "server", 3, {"name": "edge"},
         ("Server Updated", "Server 'edge' configuration has been updated.", "/servers")),
        ("server.started", "server", 3, {"name": "edge"},
         ("Server Started", "Server 'edge' is now running and accepting connections.", "/servers")),
        ("server.stopped", "server", 3, {"name": "edge"},
         ("Server Stopped", "Server 'edge' has been stopped.", "/servers")),
        ("server.reloaded", "server", 3, {"name": "edge"},
         ("Server Reloaded", "Server 'edge' configuration has been reloaded.", "/servers")),
        ("server.deleted", "server", 3, {"name": "edge"},
         ("Server Deleted", "Server 'edge' has been permanently deleted.", "/servers")),
    ],
)
def test_should_build_user_friendly_notification_when_event_type_known(
    service, event_type, source_type, source_id, payload, expected
):
    assert service._build_notification_from_event(event_type, source_type, source_id, payload) == expected


def test_should_build_generic_notification_when_event_type_unknown(service):
    title, message, link = service._build_notification_from_event(
        "plugin.custom", "plugin", 1, {}
    )

    assert title == "System Event"
    assert message == "A system event has occurred: Plugin Custom"
    assert link is None
