"""
Test fixtures and configuration for Linguard backend tests.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.main import app
from app.core.database import engine, AsyncSessionLocal, init_engine, reinit_engine, _build_engine
from app.core.config_loader import config_loader
from app.models.settings import GlobalSettings
from app.models.user import User
from app.core.security import get_current_admin


@pytest.fixture(autouse=True)
def isolated_backup_key_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    monkeypatch.delenv("LINGUARD_BACKUP_KEY_PATH", raising=False)

# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture
def test_engine():
    """Create a test database engine for async tests."""
    import os
    test_db_path = "/tmp/linguard_test.db"
    os.makedirs(os.path.dirname(test_db_path), exist_ok=True)
    
    from sqlalchemy import create_engine
    # Create sync engine for async operations
    engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
    return engine


@pytest.fixture
async def async_session():
    """Create an async session for tests."""
    import os
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import create_engine as sync_engine
    
    test_db_path = "/tmp/linguard_test.db"
    os.makedirs(os.path.dirname(test_db_path), exist_ok=True)
    
    # Create async engine
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_path}", echo=False)
    
    # Create async session maker
    async_session_maker = async_sessionmaker(async_engine, class_=AsyncSession)
    
    try:
        yield async_session_maker()
    finally:
        await async_engine.dispose()


# ============================================================================
# SHARED API TEST INFRASTRUCTURE
# ----------------------------------------------------------------------------
# Real (not mocked) SQLite database per test, wired into the FastAPI app through
# dependency overrides. Tests get an authenticated client and can freely hit
# endpoints; every request uses a fresh session against the same file so that
# commits are visible across requests, exactly like production.
#
# The TestClient is created without using it as a context manager, so the app
# lifespan (background monitors, config-file driven engine init) does not run.
# ============================================================================

import pytest_asyncio  # noqa: E402
from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.core import database as app_database  # noqa: E402
from app.core.database import Base, _build_engine, get_db  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402

# Import every model so that Base.metadata knows all tables before create_all().
from app.models.audit import *  # noqa: E402,F401,F403
from app.models.backup import *  # noqa: E402,F401,F403
from app.models.event import *  # noqa: E402,F401,F403
from app.models.integration import *  # noqa: E402,F401,F403
from app.models.notification import *  # noqa: E402,F401,F403
from app.models.peer import *  # noqa: E402,F401,F403
from app.models.plugin import *  # noqa: E402,F401,F403
from app.models.server import *  # noqa: E402,F401,F403
from app.models.settings import *  # noqa: E402,F401,F403
from app.models.traffic_metric import *  # noqa: E402,F401,F403
from app.models.traffic_trigger import *  # noqa: E402,F401,F403
from app.models.user import *  # noqa: E402,F401,F403

TEST_SECRET_KEY = "test-secret-key-for-jwt-signing"


class ApiTestState:
    """Holds the objects created by :func:`api_db` for a single test."""

    def __init__(self, engine, sessionmaker, database_url):
        self.engine = engine
        self.sessionmaker = sessionmaker
        self.database_url = database_url


@pytest_asyncio.fixture
async def api_db(tmp_path):
    """Fresh in-memory SQLite database bound to the app's database module.

    A real SQLite engine is used (real SQL, real FK enforcement) but kept in
    memory: creating the schema on a file inside WSL takes ~2s per test, while
    the in-memory variant takes ~30ms without changing semantics. ``StaticPool``
    makes every session share the same in-memory database.
    """
    from sqlalchemy import event
    from sqlalchemy.pool import StaticPool

    database_url = "sqlite+aiosqlite://"
    engine = create_async_engine(
        database_url,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = app_database.async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
        autocommit=False, autoflush=False,
    )

    state = ApiTestState(engine, sessionmaker, database_url)

    with patch.object(app_database, "engine", engine), \
         patch.object(app_database, "AsyncSessionLocal", sessionmaker):
        yield state

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(api_db):
    """A session over the per-test database, for arranging data directly."""
    async with api_db.sessionmaker() as session:
        yield session


@pytest.fixture
def api_client(api_db):
    """TestClient whose ``get_db`` dependency points at the per-test database."""

    async def _override_get_db():
        async with api_db.sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _seed_settings(session, **overrides):
    values = dict(
        secret_key=TEST_SECRET_KEY,
        algorithm="HS256",
        access_token_expire_minutes=30,
        disable_auth=False,
        auth_mode="both",
        backup_dir="./backups",
        plugins_directory="./plugins",
        log_path="./linguard.log",
        database_type="sqlite",
        setup_completed=True,
    )
    values.update(overrides)
    settings_row = GlobalSettings(**values)
    session.add(settings_row)
    await session.commit()
    return settings_row


async def _seed_user(session, username="admin", role="admin", password="admin123"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(password),
        role=role,
        auth_provider="local",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _make_headers(username):
    from jose import jwt
    from datetime import timedelta

    token = jwt.encode(
        {"sub": username, "exp": datetime.utcnow() + timedelta(minutes=30)},
        TEST_SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeded_db(api_db):
    """Settings + an admin user + a standard user, ready for authenticated calls."""
    async with api_db.sessionmaker() as session:
        await _seed_settings(session)
        admin = await _seed_user(session, "admin", "admin")
        std = await _seed_user(session, "bob", "standard")
        return {"admin_id": admin.id, "user_id": std.id}


@pytest.fixture
def admin_headers(seeded_db):
    return _make_headers("admin")


@pytest.fixture
def user_headers(seeded_db):
    return _make_headers("bob")


@pytest.fixture
def auth_client(api_client, seeded_db, admin_headers):
    """Authenticated TestClient (admin)."""
    api_client.headers.update(admin_headers)
    return api_client


@pytest.fixture
def user_client(api_client, seeded_db, user_headers):
    """Authenticated TestClient (standard, non-admin user)."""
    api_client.headers.update(user_headers)
    return api_client
