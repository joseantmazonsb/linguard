"""Tests for app.core.security: hashing, JWT issuing and auth dependencies."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import select

from app.core import database as app_database
from app.core.security import (
    create_access_token,
    get_current_admin,
    get_current_user,
    get_password_hash,
    get_settings_for_auth,
    pwd_context,
    verify_password,
)
from app.models.settings import GlobalSettings
from app.models.user import User

TEST_SECRET = "unit-test-secret"


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _add_settings(session, **overrides):
    values = dict(
        secret_key=TEST_SECRET,
        algorithm="HS256",
        access_token_expire_minutes=30,
        disable_auth=False,
        backup_dir="./backups",
        setup_completed=True,
    )
    values.update(overrides)
    row = GlobalSettings(**values)
    session.add(row)
    await session.commit()
    return row


async def _add_user(session, username="alice", role="admin", password="s3cret-pass"):
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


class TestPasswordHashing:
    def test_should_hash_and_verify_password(self):
        hashed = get_password_hash("correct horse")

        assert hashed != "correct horse"
        assert verify_password("correct horse", hashed) is True

    def test_should_reject_wrong_password(self):
        hashed = get_password_hash("correct horse")

        assert verify_password("battery staple", hashed) is False

    def test_should_truncate_password_longer_than_bcrypt_limit(self):
        password = "a" * 100

        hashed = get_password_hash(password)

        # bcrypt only considers the first 72 bytes; anything beyond must still
        # verify against the same prefix behaviour.
        assert verify_password(password, hashed) is True
        assert verify_password("a" * 80, hashed) is True
        assert verify_password("b" * 80, hashed) is False

    def test_should_use_bcrypt_scheme(self):
        hashed = pwd_context.hash("x")

        assert hashed.startswith("$2")


class TestSettingsForAuth:
    async def test_should_return_settings_when_present(self, db_session):
        await _add_settings(db_session)

        settings = await get_settings_for_auth(db_session)

        assert settings is not None
        assert settings.secret_key == TEST_SECRET

    async def test_should_return_none_when_no_settings_row(self, db_session):
        assert await get_settings_for_auth(db_session) is None


class TestCreateAccessToken:
    async def test_should_issue_jwt_signed_with_settings_secret(self, db_session):
        await _add_settings(db_session)

        token = await create_access_token({"sub": "alice"}, db_session)

        payload = jwt.decode(token, TEST_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "alice"
        assert "exp" in payload

    async def test_should_respect_custom_expiry_delta(self, db_session):
        await _add_settings(db_session)

        token = await create_access_token(
            {"sub": "alice"}, db_session, expires_delta=timedelta(minutes=5)
        )

        payload = jwt.decode(token, TEST_SECRET, algorithms=["HS256"])
        expires_at = datetime.utcfromtimestamp(payload["exp"])
        delta = expires_at - datetime.utcnow()
        assert timedelta(minutes=4) < delta <= timedelta(minutes=5)

    async def test_should_raise_503_when_application_not_configured(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            await create_access_token({"sub": "alice"}, db_session)

        assert exc_info.value.status_code == 503


class TestGetCurrentUser:
    async def test_should_return_user_for_valid_token(self, db_session):
        await _add_settings(db_session)
        user = await _add_user(db_session)

        token = jwt.encode({"sub": user.username}, TEST_SECRET, algorithm="HS256")

        assert (await get_current_user(_credentials(token), db_session)).id == user.id

    async def test_should_raise_401_when_credentials_missing(self, db_session):
        await _add_settings(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None, db_session)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    async def test_should_raise_401_when_token_signature_invalid(self, db_session):
        await _add_settings(db_session)
        await _add_user(db_session)
        token = jwt.encode({"sub": "alice"}, "wrong-secret", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(_credentials(token), db_session)

        assert exc_info.value.status_code == 401

    async def test_should_raise_401_when_token_expired(self, db_session):
        await _add_settings(db_session)
        await _add_user(db_session)
        token = jwt.encode(
            {"sub": "alice", "exp": datetime.utcnow() - timedelta(minutes=1)},
            TEST_SECRET,
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(_credentials(token), db_session)

        assert exc_info.value.status_code == 401

    async def test_should_raise_401_when_token_has_no_subject(self, db_session):
        await _add_settings(db_session)
        token = jwt.encode({"foo": "bar"}, TEST_SECRET, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(_credentials(token), db_session)

        assert exc_info.value.status_code == 401

    async def test_should_raise_401_when_user_no_longer_exists(self, db_session):
        await _add_settings(db_session)
        token = jwt.encode({"sub": "ghost"}, TEST_SECRET, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(_credentials(token), db_session)

        assert exc_info.value.status_code == 401

    async def test_should_raise_503_when_settings_missing_but_token_supplied(
        self, db_session
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(_credentials("anything"), db_session)

        assert exc_info.value.status_code == 503


class TestGetCurrentUserWithAuthDisabled:
    async def test_should_return_existing_user_when_auth_disabled(self, db_session):
        await _add_settings(db_session, disable_auth=True)
        user = await _add_user(db_session)

        assert (await get_current_user(None, db_session)).id == user.id

    async def test_should_create_temp_admin_when_auth_disabled_and_no_users(
        self, db_session
    ):
        await _add_settings(db_session, disable_auth=True)

        user = await get_current_user(None, db_session)

        assert user.username == "admin"
        result = await db_session.execute(select(User))
        assert len(result.scalars().all()) == 1


class TestGetCurrentAdmin:
    async def test_should_return_admin_user(self):
        user = User(username="a", email="a@x", role="admin")

        assert await get_current_admin(user) is user

    async def test_should_raise_403_for_standard_user(self):
        user = User(username="b", email="b@x", role="standard")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin(user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Administrator privileges required"


class TestDatabaseModule:
    async def test_should_build_engine_with_foreign_keys_enabled(self, tmp_path):
        engine = app_database._build_engine(f"sqlite+aiosqlite:///{tmp_path}/fk.db")
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text

                value = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
            assert value == 1
        finally:
            await engine.dispose()

    async def test_should_raise_when_get_db_used_before_init(self, monkeypatch):
        monkeypatch.setattr(app_database, "AsyncSessionLocal", None)

        generator = app_database.get_db()
        with pytest.raises(RuntimeError):
            await generator.__anext__()

    async def test_should_commit_session_when_generator_completes(self, api_db):
        generator = app_database.get_db()
        session = await generator.__anext__()
        session.add(GlobalSettings(secret_key="committed-by-get-db", backup_dir="./b"))

        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

        async with app_database.AsyncSessionLocal() as check:
            result = await check.execute(
                select(GlobalSettings).where(
                    GlobalSettings.secret_key == "committed-by-get-db"
                )
            )
            assert result.scalars().first() is not None

    async def test_should_rollback_when_body_raises(self, api_db):
        generator = app_database.get_db()
        session = await generator.__anext__()
        session.add(GlobalSettings(secret_key="rollback-me", backup_dir="./b"))

        with pytest.raises(RuntimeError):
            await generator.athrow(RuntimeError("boom"))

        async with app_database.AsyncSessionLocal() as check:
            result = await check.execute(
                select(GlobalSettings).where(GlobalSettings.secret_key == "rollback-me")
            )
            assert result.scalars().first() is None

    async def test_should_create_all_tables_via_init_db(self, api_db):
        async with app_database.engine.begin() as conn:
            await conn.run_sync(app_database.Base.metadata.drop_all)

        await app_database.init_db()

        async with app_database.engine.begin() as conn:
            names = await conn.run_sync(lambda sync: sync.dialect.get_table_names(sync))
        assert "users" in names and "peers" in names

    async def test_should_raise_when_init_db_called_without_engine(self, monkeypatch):
        monkeypatch.setattr(app_database, "engine", None)

        with pytest.raises(RuntimeError):
            await app_database.init_db()

    async def test_should_raise_when_init_engine_without_config(self, monkeypatch):
        monkeypatch.setattr(
            app_database.config_loader, "exists", lambda: False
        )

        with pytest.raises(RuntimeError):
            app_database.init_engine()

    def test_should_init_engine_from_config_file(self, tmp_path, monkeypatch):
        db_path = tmp_path / "cfg.db"
        monkeypatch.setattr(app_database.config_loader, "exists", lambda: True)
        monkeypatch.setattr(
            app_database.config_loader,
            "get_database_url",
            lambda: f"sqlite+aiosqlite:///{db_path}",
        )

        original_engine = app_database.engine
        try:
            app_database.init_engine()
            assert app_database.engine is not None
            assert app_database.AsyncSessionLocal is not None
        finally:
            app_database.engine = original_engine

    def test_should_replace_engine_on_reinit(self, api_db, tmp_path):
        new_url = f"sqlite+aiosqlite:///{tmp_path}/reinit.db"

        app_database.reinit_engine(new_url)

        assert Path(app_database.engine.url.database) == tmp_path / "reinit.db"
