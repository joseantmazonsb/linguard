"""Tests for local login, profile, password change and user management."""

from datetime import datetime, timedelta

import pytest
from jose import jwt
from sqlalchemy import select

from app.core.security import get_password_hash, verify_password
from app.models.audit import AuditLog
from app.models.settings import GlobalSettings
from app.models.user import User

JWT_SECRET = "test-secret-key-for-jwt-signing"

TOKEN_URL = "/api/v1/auth/token"
PROFILE_URL = "/api/v1/auth/profile"
CHANGE_PASSWORD_URL = "/api/v1/auth/change-password"
USERS_URL = "/api/v1/auth/users"


async def _add_user(session, username, password="secret123", **overrides):
    values = dict(
        username=username,
        email=overrides.pop("email", f"{username}@example.com"),
        hashed_password=None if password is None else get_password_hash(password),
        role="standard",
        auth_provider="local",
    )
    values.update(overrides)
    user = User(**values)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# POST /token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_issue_usable_token_when_credentials_are_valid(api_client, seeded_db):
    response = api_client.post(
        TOKEN_URL, data={"username": "admin", "password": "admin123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "admin"
    assert "hashed_password" not in body["user"]

    profile = api_client.get(
        PROFILE_URL, headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert profile.status_code == 200
    assert profile.json()["username"] == "admin"
    assert profile.json()["email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_should_record_success_audit_when_login_succeeds(api_client, db_session, seeded_db):
    api_client.post(TOKEN_URL, data={"username": "admin", "password": "admin123"})

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "LOGIN"))
    ).scalars().one()
    assert audit.status == "success"
    assert audit.details == {"method": "local"}
    assert audit.resource_name == "admin"


@pytest.mark.asyncio
async def test_should_reject_login_when_password_is_wrong(api_client, db_session, seeded_db):
    response = api_client.post(TOKEN_URL, data={"username": "admin", "password": "nope"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"
    assert response.headers["WWW-Authenticate"] == "Bearer"

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "LOGIN"))
    ).scalars().one()
    await db_session.refresh(audit)
    assert audit.status == "failed"
    assert audit.error_message == "Incorrect username or password"


@pytest.mark.asyncio
async def test_should_reject_login_without_audit_user_when_username_unknown(api_client, db_session, seeded_db):
    response = api_client.post(TOKEN_URL, data={"username": "ghost", "password": "whatever"})

    assert response.status_code == 401
    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "LOGIN"))
    ).scalars().one()
    await db_session.refresh(audit)
    assert audit.user_id is None
    assert audit.status == "failed"
    assert audit.resource_name is None


@pytest.mark.asyncio
async def test_should_reject_login_when_account_has_no_local_password(api_client, db_session, seeded_db):
    await _add_user(db_session, "oidcuser", password=None, auth_provider="oidc")

    response = api_client.post(TOKEN_URL, data={"username": "oidcuser", "password": "secret123"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_should_reject_local_login_when_account_is_oidc_linked(api_client, db_session, seeded_db):
    # An OIDC-linked account keeps a (now unused) local hash; local login must
    # still be refused with a pointer to the identity provider.
    await _add_user(db_session, "oidcuser", password="secret123", auth_provider="oidc")

    response = api_client.post(TOKEN_URL, data={"username": "oidcuser", "password": "secret123"})

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "This account uses Single Sign-On. Sign in with your identity provider."
    )
    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "LOGIN"))
    ).scalars().one()
    await db_session.refresh(audit)
    assert audit.error_message == "OIDC account attempted local login"


@pytest.mark.asyncio
async def test_should_reject_local_login_when_auth_mode_is_oidc_only(api_client, db_session, seeded_db):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.auth_mode = "oidc_only"
    await db_session.commit()

    response = api_client.post(TOKEN_URL, data={"username": "admin", "password": "admin123"})

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Local password login is disabled (OIDC-only mode). Sign in with your identity provider."
    )


@pytest.mark.asyncio
async def test_should_return_503_when_settings_table_is_missing(api_client, db_session, seeded_db):
    """A half-migrated database (no global_settings) cannot mint tokens."""
    from sqlalchemy import text

    await db_session.execute(text("DROP TABLE global_settings"))
    await db_session.commit()

    response = api_client.post(TOKEN_URL, data={"username": "admin", "password": "admin123"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Application not configured. Please complete setup first."


# ---------------------------------------------------------------------------
# GET /profile, PUT /profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_reject_profile_when_no_token_provided(api_client, seeded_db):
    response = api_client.get(PROFILE_URL)

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
async def test_should_reject_profile_when_token_is_signed_with_other_key(api_client, seeded_db):
    bad = jwt.encode({"sub": "admin"}, "some-other-secret", algorithm="HS256")

    response = api_client.get(PROFILE_URL, headers={"Authorization": f"Bearer {bad}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_should_reject_profile_when_token_has_no_subject(api_client, seeded_db):
    token = jwt.encode({"exp": 9999999999}, JWT_SECRET, algorithm="HS256")

    response = api_client.get(PROFILE_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_should_reject_profile_when_token_subject_does_not_exist(api_client, seeded_db):
    response = api_client.get(
        PROFILE_URL,
        headers={
            "Authorization": "Bearer "
            + jwt.encode(
                {"sub": "deleted-user", "exp": 9999999999},
                JWT_SECRET,
                algorithm="HS256",
            )
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_should_return_503_when_settings_missing_and_profile_requested(api_db, api_client, db_session):
    await _add_user(db_session, "lonely")
    token = jwt.encode(
        {"sub": "lonely", "exp": datetime.utcnow() + timedelta(minutes=5)},
        "any-secret",
        algorithm="HS256",
    )

    response = api_client.get(PROFILE_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Application not configured. Please complete setup first."


@pytest.mark.asyncio
async def test_should_return_first_user_when_auth_is_disabled(api_client, db_session, seeded_db):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()

    response = api_client.get(PROFILE_URL)

    assert response.status_code == 200
    assert response.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_should_create_temporary_admin_when_auth_disabled_and_no_user_exists(api_client, db_session, seeded_db):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    for user in (await db_session.execute(select(User))).scalars().all():
        await db_session.delete(user)
    await db_session.commit()

    response = api_client.get(PROFILE_URL)

    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert (await db_session.execute(select(User))).scalars().all() != []


@pytest.mark.asyncio
async def test_should_update_email_when_profile_updated(auth_client, db_session):
    response = auth_client.put(PROFILE_URL, json={"email": "new-admin@example.com"})

    assert response.status_code == 200
    assert response.json()["email"] == "new-admin@example.com"
    user = (await db_session.execute(select(User).where(User.username == "admin"))).scalars().one()
    await db_session.refresh(user)
    assert user.email == "new-admin@example.com"


@pytest.mark.asyncio
async def test_should_reject_profile_update_when_email_belongs_to_another_user(auth_client):
    response = auth_client.put(PROFILE_URL, json={"email": "bob@example.com"})

    assert response.status_code == 422
    assert response.json()["errors"] == {"body.email": ["Email already registered"]}


@pytest.mark.asyncio
async def test_should_reject_profile_update_when_email_is_invalid(auth_client):
    response = auth_client.put(PROFILE_URL, json={"email": "not-an-email"})

    assert response.status_code == 422
    assert "body.email" in response.json()["errors"]


# ---------------------------------------------------------------------------
# POST /change-password
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_change_password_when_current_password_is_correct(api_client, db_session, auth_client):
    response = auth_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": "admin123", "new_password": "brandnew123"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password changed successfully"}

    user = (await db_session.execute(select(User).where(User.username == "admin"))).scalars().one()
    await db_session.refresh(user)
    assert verify_password("brandnew123", user.hashed_password)
    assert not verify_password("admin123", user.hashed_password)

    # The new password is accepted end-to-end and the old one is not.
    assert api_client.post(
        TOKEN_URL, data={"username": "admin", "password": "brandnew123"}
    ).status_code == 200
    assert api_client.post(
        TOKEN_URL, data={"username": "admin", "password": "admin123"}
    ).status_code == 401


@pytest.mark.asyncio
async def test_should_reject_password_change_when_current_password_is_wrong(auth_client, db_session):
    response = auth_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": "wrongpass", "new_password": "brandnew123"},
    )

    assert response.status_code == 422
    assert response.json()["errors"] == {"body.current_password": ["Current password is incorrect"]}
    user = (await db_session.execute(select(User).where(User.username == "admin"))).scalars().one()
    await db_session.refresh(user)
    assert verify_password("admin123", user.hashed_password)


@pytest.mark.asyncio
async def test_should_reject_password_change_when_new_password_is_too_short(auth_client):
    response = auth_client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": "admin123", "new_password": "123"},
    )

    assert response.status_code == 422
    assert response.json()["errors"] == {
        "body.new_password": ["New password must be at least 6 characters long"]
    }


@pytest.mark.asyncio
async def test_should_reject_password_change_when_account_is_sso_only(api_client, db_session, seeded_db):
    user = await _add_user(db_session, "ssouser", password=None, auth_provider="oidc")
    from app.core.security import create_access_token

    token = await create_access_token({"sub": user.username}, db=db_session)

    response = api_client.post(
        CHANGE_PASSWORD_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "whatever", "new_password": "brandnew123"},
    )

    assert response.status_code == 422
    assert response.json()["errors"] == {
        "body.current_password": [
            "This account signs in with Single Sign-On and has no local password"
        ]
    }


# ---------------------------------------------------------------------------
# GET /users, PUT /users/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_list_users_when_admin_requests_them(auth_client):
    response = auth_client.get(USERS_URL)

    assert response.status_code == 200
    body = response.json()
    assert [u["username"] for u in body] == ["admin", "bob"]
    assert set(body[0]) == {"id", "username", "email", "role", "auth_provider"}


@pytest.mark.asyncio
async def test_should_deny_user_listing_when_requester_is_standard_user(user_client):
    response = user_client.get(USERS_URL)

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"


@pytest.mark.asyncio
async def test_should_deny_user_listing_when_unauthenticated(api_client, seeded_db):
    assert api_client.get(USERS_URL).status_code == 401


@pytest.mark.asyncio
async def test_should_promote_user_when_admin_updates_role(auth_client, db_session, seeded_db):
    response = auth_client.put(f"{USERS_URL}/{seeded_db['user_id']}", json={"role": "admin"})

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    user = (await db_session.execute(select(User).where(User.id == seeded_db["user_id"]))).scalars().one()
    await db_session.refresh(user)
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_should_return_404_when_admin_updates_unknown_user(auth_client):
    response = auth_client.put(f"{USERS_URL}/9999", json={"role": "admin"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_should_refuse_demotion_when_user_is_last_admin(auth_client, seeded_db):
    response = auth_client.put(f"{USERS_URL}/{seeded_db['admin_id']}", json={"role": "standard"})

    assert response.status_code == 422
    assert response.json()["errors"] == {"body.role": ["Cannot demote the last administrator"]}


@pytest.mark.asyncio
async def test_should_allow_demotion_when_another_admin_exists(auth_client, db_session, seeded_db):
    await _add_user(db_session, "secondadmin", role="admin")

    response = auth_client.put(f"{USERS_URL}/{seeded_db['admin_id']}", json={"role": "standard"})

    assert response.status_code == 200
    assert response.json()["role"] == "standard"


@pytest.mark.asyncio
async def test_should_reject_unknown_role_when_admin_updates_user(auth_client, seeded_db):
    response = auth_client.put(f"{USERS_URL}/{seeded_db['user_id']}", json={"role": "superuser"})

    assert response.status_code == 422
    assert "body.role" in response.json()["errors"]


@pytest.mark.asyncio
async def test_should_deny_role_update_when_requester_is_standard_user(user_client, seeded_db):
    response = user_client.put(f"{USERS_URL}/{seeded_db['user_id']}", json={"role": "admin"})

    assert response.status_code == 403
