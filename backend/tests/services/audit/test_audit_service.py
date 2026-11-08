"""Tests for AuditService: persisted audit rows and change-detail helpers."""
import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit_logger import AuditService


class FakeRequest:
    """Minimal stand-in for a Starlette Request (only what AuditService reads)."""

    def __init__(self, host="203.0.113.7", headers=None, client=True):
        self.headers = headers if headers is not None else {"user-agent": "pytest/1.0"}
        self.client = type("Client", (), {"host": host})() if client else None


@pytest.fixture
def service():
    return AuditService()


@pytest.fixture
async def user(db_session):
    row = User(
        username="auditor",
        email="auditor@example.com",
        hashed_password="x",
        role="admin",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


class TestLogAction:
    async def test_should_persist_request_metadata(self, service, db_session, user):
        await service.log_action(
            db_session,
            user=user,
            action="CREATE",
            resource_type="peer",
            resource_id=7,
            resource_name="laptop",
            details={"ip": "10.0.0.2"},
            request=FakeRequest(),
        )
        await db_session.commit()

        rows = (await db_session.execute(select(AuditLog))).scalars().all()
        assert len(rows) == 1
        log = rows[0]
        assert (log.user_id, log.action, log.resource_type) == (user.id, "CREATE", "peer")
        assert log.resource_id == 7
        assert log.resource_name == "laptop"
        assert log.ip_address == "203.0.113.7"
        assert log.user_agent == "pytest/1.0"
        assert log.status == "success"
        assert log.error_message is None

    async def test_should_store_no_metadata_when_request_is_none(
        self, service, db_session, user
    ):
        await service.log_action(
            db_session,
            user=user,
            action="DELETE",
            resource_type="server",
            resource_id=None,
            resource_name=None,
            details=None,
        )
        await db_session.commit()

        log = (await db_session.execute(select(AuditLog))).scalars().one()
        assert log.ip_address is None
        assert log.user_agent is None

    async def test_should_handle_request_without_client(self, service, db_session, user):
        await service.log_action(
            db_session,
            user=user,
            action="UPDATE",
            resource_type="settings",
            resource_id=1,
            resource_name="global",
            details=None,
            request=FakeRequest(client=False),
        )
        await db_session.commit()

        log = (await db_session.execute(select(AuditLog))).scalars().one()
        assert log.ip_address is None
        assert log.user_agent == "pytest/1.0"

    async def test_should_record_failed_status_and_error_message(
        self, service, db_session, user
    ):
        await service.log_action(
            db_session,
            user=user,
            action="LOGIN",
            resource_type="user",
            resource_id=user.id,
            resource_name=user.username,
            details=None,
            status="failed",
            error_message="bad password",
        )
        await db_session.commit()

        log = (await db_session.execute(select(AuditLog))).scalars().one()
        assert log.status == "failed"
        assert log.error_message == "bad password"

    async def test_should_flush_before_commit_so_row_is_visible_in_transaction(
        self, service, db_session, user
    ):
        await service.log_action(
            db_session, user, "CREATE", "peer", 1, "p", None
        )

        rows = (await db_session.execute(select(AuditLog))).scalars().all()
        assert len(rows) == 1


class TestCreateChangeDetails:
    def test_should_report_changed_fields_as_before_after(self, service):
        details = service.create_change_details(
            {"name": "old", "port": 51820}, {"name": "new", "port": 51820}
        )

        assert details["changes"] == {"name": {"from": "old", "to": "new"}}
        assert details["before"] == {"name": "old", "port": 51820}
        assert details["after"] == {"name": "new", "port": 51820}

    def test_should_report_added_and_removed_fields(self, service):
        details = service.create_change_details({"a": 1}, {"b": 2})

        assert details["changes"] == {
            "a": {"from": 1, "to": None},
            "b": {"from": None, "to": 2},
        }

    def test_should_return_no_changes_when_values_are_equal(self, service):
        details = service.create_change_details({"a": 1}, {"a": 1})

        assert details["changes"] == {}
