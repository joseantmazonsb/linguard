"""Tests for ``app/api/audit.py``.

Audit rows are inserted directly into the real per-test database (that is how
the audit service writes them) and then queried through the API so filtering,
ordering, pagination and aggregation all run against real SQL.
"""

from datetime import datetime, timedelta, timezone

import pytest_asyncio

from app.models.audit import AuditLog

BASE = "/api/v1/audit"


@pytest_asyncio.fixture
async def audit_logs(db_session, seeded_db):
    """A handful of audit entries covering every filter dimension."""
    admin_id = seeded_db["admin_id"]
    bob_id = seeded_db["user_id"]
    now = datetime.now(timezone.utc)

    rows = [
        AuditLog(
            user_id=admin_id,
            action="CREATE",
            resource_type="server",
            resource_id=1,
            resource_name="srv-main",
            details={"interface": "wg0"},
            ip_address="10.0.0.5",
            user_agent="pytest",
            status="success",
            timestamp=now - timedelta(hours=3),
        ),
        AuditLog(
            user_id=admin_id,
            action="DELETE",
            resource_type="peer",
            resource_id=7,
            resource_name="peer-main",
            details=None,
            ip_address="10.0.0.5",
            status="success",
            timestamp=now - timedelta(hours=2),
        ),
        AuditLog(
            user_id=bob_id,
            action="UPDATE",
            resource_type="server",
            resource_id=1,
            resource_name="srv-main",
            details={"name": {"from": "old", "to": "new"}},
            ip_address="192.168.1.20",
            status="failed",
            error_message="permission denied by firewall",
            timestamp=now - timedelta(hours=1),
        ),
        AuditLog(
            user_id=None,
            action="LOGIN",
            resource_type="user",
            resource_id=None,
            resource_name="anonymous",
            ip_address="203.0.113.9",
            status="failed",
            error_message="bad credentials",
            timestamp=now,
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    for row in rows:
        await db_session.refresh(row)
    return {"rows": rows, "admin_id": admin_id, "bob_id": bob_id, "now": now}


async def _ids(response):
    return [entry["id"] for entry in response.json()]


# ---------------------------------------------------------------------------
# List & filters
# ---------------------------------------------------------------------------

async def test_should_list_logs_newest_first_with_usernames(auth_client, audit_logs):
    response = auth_client.get(BASE + "/")

    assert response.status_code == 200
    body = response.json()
    assert [entry["action"] for entry in body] == ["LOGIN", "UPDATE", "DELETE", "CREATE"]
    assert [entry["username"] for entry in body] == ["Unknown", "bob", "admin", "admin"]
    assert body[1]["details"] == {"name": {"from": "old", "to": "new"}}
    assert body[0]["created_at"] is not None


async def test_should_filter_logs_when_action_and_resource_filters_are_given(
    auth_client, audit_logs
):
    rows = audit_logs["rows"]

    by_action = auth_client.get(BASE + "/", params={"action": "update"})
    assert await _ids(by_action) == [rows[2].id]

    by_type = auth_client.get(BASE + "/", params={"resource_type": "SERVER"})
    assert set(await _ids(by_type)) == {rows[0].id, rows[2].id}

    by_resource = auth_client.get(
        BASE + "/", params={"resource_type": "server", "resource_id": 1}
    )
    assert set(await _ids(by_resource)) == {rows[0].id, rows[2].id}

    by_user = auth_client.get(BASE + "/", params={"user_id": audit_logs["admin_id"]})
    assert await _ids(by_user) == [rows[1].id, rows[0].id]

    no_matches = auth_client.get(BASE + "/", params={"action": "MIGRATE"})
    assert no_matches.json() == []


async def test_should_filter_logs_when_date_range_is_given(auth_client, audit_logs):
    rows = audit_logs["rows"]
    now = audit_logs["now"]

    response = auth_client.get(
        BASE + "/",
        params={
            "start_date": (now - timedelta(hours=2, minutes=30)).isoformat(),
            "end_date": (now - timedelta(minutes=30)).isoformat(),
        },
    )

    assert await _ids(response) == [rows[2].id, rows[1].id]


async def test_should_search_logs_when_text_matches_any_column(auth_client, audit_logs):
    rows = audit_logs["rows"]

    by_name = auth_client.get(BASE + "/", params={"search": "peer-main"})
    assert await _ids(by_name) == [rows[1].id]

    by_username = auth_client.get(BASE + "/", params={"search": "bob"})
    assert await _ids(by_username) == [rows[2].id]

    by_ip = auth_client.get(BASE + "/", params={"search": "203.0.113"})
    assert await _ids(by_ip) == [rows[3].id]

    by_error = auth_client.get(BASE + "/", params={"search": "firewall"})
    assert await _ids(by_error) == [rows[2].id]

    by_resource_type = auth_client.get(BASE + "/", params={"search": "peer"})
    assert await _ids(by_resource_type) == [rows[1].id]


async def test_should_paginate_logs_when_skip_and_limit_are_given(auth_client, audit_logs):
    rows = audit_logs["rows"]

    response = auth_client.get(BASE + "/", params={"skip": 1, "limit": 2})

    assert await _ids(response) == [rows[2].id, rows[1].id]


async def test_should_reject_invalid_pagination_when_limits_are_out_of_range(
    auth_client, audit_logs
):
    assert auth_client.get(BASE + "/", params={"limit": 0}).status_code == 422
    assert auth_client.get(BASE + "/", params={"limit": 1001}).status_code == 422
    assert auth_client.get(BASE + "/", params={"skip": -1}).status_code == 422


# ---------------------------------------------------------------------------
# Single log, per-resource and per-user history
# ---------------------------------------------------------------------------

async def test_should_get_log_by_id_when_it_exists(auth_client, audit_logs):
    row = audit_logs["rows"][2]

    response = auth_client.get(f"{BASE}/{row.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == row.id
    assert body["action"] == "UPDATE"
    assert body["username"] == "bob"
    assert body["status"] == "failed"
    assert body["error_message"] == "permission denied by firewall"
    assert body["created_at"] == body["timestamp"]


async def test_should_get_log_without_resource_when_resource_id_is_null(auth_client, audit_logs):
    row = audit_logs["rows"][3]

    response = auth_client.get(f"{BASE}/{row.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["resource_id"] is None
    assert body["user_id"] is None
    assert body["username"] == "Unknown"


async def test_should_return_404_when_log_does_not_exist(auth_client, audit_logs):
    assert auth_client.get(f"{BASE}/9999").status_code == 404


async def test_should_list_resource_history_when_entries_exist(auth_client, audit_logs):
    rows = audit_logs["rows"]

    response = auth_client.get(f"{BASE}/resource/server/1")

    assert response.status_code == 200
    assert await _ids(response) == [rows[2].id, rows[0].id]
    assert all(entry["username"] in {"admin", "bob"} for entry in response.json())


async def test_should_return_empty_resource_history_when_type_is_unknown(
    auth_client, audit_logs
):
    assert auth_client.get(f"{BASE}/resource/backup/123").json() == []


async def test_should_list_user_actions_when_user_exists(auth_client, audit_logs):
    response = auth_client.get(f"{BASE}/user/{audit_logs['admin_id']}/actions")

    assert response.status_code == 200
    assert await _ids(response) == [audit_logs["rows"][1].id, audit_logs["rows"][0].id]

    paged = auth_client.get(
        f"{BASE}/user/{audit_logs['admin_id']}/actions", params={"skip": 1, "limit": 1}
    )
    assert await _ids(paged) == [audit_logs["rows"][0].id]


async def test_should_return_empty_user_actions_when_user_has_none(auth_client, audit_logs):
    assert auth_client.get(f"{BASE}/user/4242/actions").json() == []


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

async def test_should_summarise_audit_logs_when_entries_exist(auth_client, audit_logs):
    response = auth_client.get(BASE + "/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_logs"] == 4
    assert body["actions_by_type"] == {"CREATE": 1, "DELETE": 1, "UPDATE": 1, "LOGIN": 1}
    assert body["resources_by_type"] == {"server": 2, "peer": 1, "user": 1}
    assert body["top_users"][0] == {"user_id": audit_logs["admin_id"], "action_count": 2}
    assert {"user_id": audit_logs["bob_id"], "action_count": 1} in body["top_users"]
    assert body["date_range"] == {"start": None, "end": None}


async def test_should_summarise_audit_logs_within_date_range_when_filters_are_given(
    auth_client, audit_logs
):
    now = audit_logs["now"]
    start = now - timedelta(hours=1, minutes=30)

    response = auth_client.get(
        BASE + "/stats/summary",
        params={"start_date": start.isoformat(), "end_date": now.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_logs"] == 2
    assert body["actions_by_type"] == {"UPDATE": 1, "LOGIN": 1}
    assert body["date_range"]["start"] is not None
    assert body["date_range"]["end"] is not None


async def test_should_return_empty_summary_when_no_logs_exist(auth_client, seeded_db):
    response = auth_client.get(BASE + "/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_logs"] == 0
    assert body["actions_by_type"] == {}
    assert body["resources_by_type"] == {}
    assert body["top_users"] == []


async def test_should_require_authentication_when_listing_audit_logs(api_client, seeded_db):
    assert api_client.get(BASE + "/").status_code == 401
