"""Tests for the OIDC / Single Sign-On endpoints."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.api.auth import oidc_service
from app.models.audit import AuditLog
from app.models.settings import GlobalSettings
from app.models.user import User

CONFIG_URL = "/api/v1/auth/oidc/config"
LOGIN_URL = "/api/v1/auth/oidc/login"
CALLBACK_URL = "/api/v1/auth/oidc/callback"
TEST_URL = "/api/v1/auth/oidc/test"
PROFILE_URL = "/api/v1/auth/profile"

DISCOVERY = {
    "issuer": "https://authentik.example.com/application/o/linguard/",
    "authorization_endpoint": "https://authentik.example.com/application/o/authorize/",
    "token_endpoint": "https://authentik.example.com/application/o/token/",
    "jwks_uri": "https://authentik.example.com/application/o/jwks/",
}


async def _configure_oidc(session, **overrides):
    settings = (await session.execute(select(GlobalSettings))).scalar_one()
    settings.auth_mode = "both"
    settings.oidc_discovery_url = "https://authentik.example.com/.well-known/openid-configuration"
    settings.oidc_client_id = "linguard-client"
    settings.oidc_client_secret = "s3cret"
    settings.oidc_scopes = "openid email profile"
    for key, value in overrides.items():
        setattr(settings, key, value)
    await session.commit()
    return settings


# ---------------------------------------------------------------------------
# GET /oidc/config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_report_oidc_disabled_when_no_settings_exist(api_client):
    response = api_client.get(CONFIG_URL)

    assert response.status_code == 200
    assert response.json() == {"oidc_enabled": False, "auth_mode": "both", "provider_name": None}


@pytest.mark.asyncio
async def test_should_report_oidc_disabled_when_auth_mode_is_local_only(api_client, db_session, seeded_db):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.auth_mode = "local_only"
    settings.oidc_discovery_url = "https://idp.example.com/.well-known/openid-configuration"
    await db_session.commit()

    response = api_client.get(CONFIG_URL)

    assert response.json() == {
        "oidc_enabled": False,
        "auth_mode": "local_only",
        "provider_name": None,
    }


@pytest.mark.asyncio
async def test_should_report_oidc_disabled_when_discovery_url_is_unset(api_client, seeded_db):
    response = api_client.get(CONFIG_URL)

    assert response.json()["oidc_enabled"] is False
    assert response.json()["auth_mode"] == "both"


@pytest.mark.asyncio
async def test_should_report_provider_name_from_discovery_when_oidc_configured(
    api_client, db_session, seeded_db, monkeypatch
):
    await _configure_oidc(db_session)
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))

    response = api_client.get(CONFIG_URL)

    assert response.json() == {
        "oidc_enabled": True,
        "auth_mode": "both",
        "provider_name": "Authentik",
    }


@pytest.mark.asyncio
async def test_should_prefer_configured_provider_name_when_oidc_configured(
    api_client, db_session, seeded_db, monkeypatch
):
    await _configure_oidc(db_session, oidc_provider_name="Corp SSO")
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))

    response = api_client.get(CONFIG_URL)

    assert response.json()["provider_name"] == "Corp SSO"


@pytest.mark.asyncio
async def test_should_still_enable_button_when_discovery_is_unreachable(
    api_client, db_session, seeded_db, monkeypatch
):
    from app.services.oidc_service import OIDCError

    await _configure_oidc(db_session, oidc_provider_name="Corp SSO")
    monkeypatch.setattr(
        oidc_service, "get_discovery", AsyncMock(side_effect=OIDCError("unreachable"))
    )

    response = api_client.get(CONFIG_URL)

    assert response.json() == {
        "oidc_enabled": True,
        "auth_mode": "both",
        "provider_name": "Corp SSO",
    }


# ---------------------------------------------------------------------------
# GET /oidc/login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_return_404_when_sso_not_configured(api_client):
    response = api_client.get(LOGIN_URL)

    assert response.status_code == 404
    assert response.json()["detail"] == "Single Sign-On is not configured"


@pytest.mark.asyncio
async def test_should_return_404_when_auth_mode_is_local_only(api_client, db_session, seeded_db, monkeypatch):
    await _configure_oidc(db_session, auth_mode="local_only")
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))

    response = api_client.get(LOGIN_URL)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_should_return_404_when_client_id_is_missing(api_client, db_session, seeded_db):
    await _configure_oidc(db_session, oidc_client_id=None)

    response = api_client.get(LOGIN_URL)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_should_build_authorization_url_from_origin_header(api_client, db_session, seeded_db, monkeypatch):
    await _configure_oidc(db_session)
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))

    response = api_client.get(LOGIN_URL, headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    url = response.json()["authorization_url"]
    assert url.startswith(DISCOVERY["authorization_endpoint"] + "?")
    assert "client_id=linguard-client" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A5173%2Foidc-callback" in url
    assert "code_challenge_method=S256" in url
    assert "response_type=code" in url
    assert "scope=openid+email+profile" in url
    assert "state=" in url


@pytest.mark.asyncio
async def test_should_derive_origin_from_referer_when_no_origin_header(
    api_client, db_session, seeded_db, monkeypatch
):
    await _configure_oidc(db_session, oidc_scopes="")
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))

    response = api_client.get(
        LOGIN_URL, headers={"Referer": "https://linguard.example.com/login?next=/servers"}
    )

    url = response.json()["authorization_url"]
    assert "redirect_uri=https%3A%2F%2Flinguard.example.com%2Foidc-callback" in url
    assert "scope=openid+email+profile" in url


@pytest.mark.asyncio
async def test_should_fall_back_to_request_base_url_when_no_origin_or_referer(
    api_client, db_session, seeded_db, monkeypatch
):
    await _configure_oidc(db_session)
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))

    response = api_client.get(LOGIN_URL)

    url = response.json()["authorization_url"]
    assert "redirect_uri=http%3A%2F%2Ftestserver%2Foidc-callback" in url


@pytest.mark.asyncio
async def test_should_return_502_when_provider_discovery_fails(api_client, db_session, seeded_db, monkeypatch):
    from app.services.oidc_service import OIDCError

    await _configure_oidc(db_session)
    monkeypatch.setattr(
        oidc_service,
        "get_discovery",
        AsyncMock(side_effect=OIDCError("Could not reach discovery URL: timeout")),
    )

    response = api_client.get(LOGIN_URL)

    assert response.status_code == 502
    assert response.json()["detail"] == "Could not reach discovery URL: timeout"


# ---------------------------------------------------------------------------
# POST /oidc/callback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_return_404_when_callback_without_settings(api_client):
    response = api_client.post(CALLBACK_URL, json={"code": "abc", "state": "xyz"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Single Sign-On is not configured"


@pytest.mark.asyncio
async def test_should_return_404_when_callback_without_discovery_url(api_client, seeded_db):
    response = api_client.post(CALLBACK_URL, json={"code": "abc", "state": "xyz"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_should_return_401_and_audit_when_callback_state_is_invalid(
    api_client, db_session, seeded_db, monkeypatch
):
    from app.services.oidc_service import OIDCError

    await _configure_oidc(db_session)
    monkeypatch.setattr(
        oidc_service,
        "pop_flow",
        lambda state: (_ for _ in ()).throw(OIDCError("Invalid or expired login state. Please try signing in again.")),
    )

    response = api_client.post(CALLBACK_URL, json={"code": "abc", "state": "bogus"})

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired login state. Please try signing in again."
    )
    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "LOGIN"))
    ).scalars().one()
    await db_session.refresh(audit)
    assert audit.user_id is None
    assert audit.status == "failed"
    assert audit.details == {"method": "oidc"}
    assert audit.error_message == "Invalid or expired login state. Please try signing in again."


@pytest.mark.asyncio
async def test_should_provision_user_and_issue_token_when_callback_succeeds(
    api_client, db_session, seeded_db, monkeypatch
):
    await _configure_oidc(db_session)
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("verifier-1", "http://testserver/oidc-callback"))
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(
        oidc_service,
        "exchange_code",
        AsyncMock(return_value={"id_token": "id-token", "access_token": "access"}),
    )
    monkeypatch.setattr(
        oidc_service,
        "obtain_claims",
        AsyncMock(
            return_value={
                "sub": "idp-subject-1",
                "email": "newbie@example.com",
                "preferred_username": "newbie",
            }
        ),
    )

    response = api_client.post(CALLBACK_URL, json={"code": "auth-code", "state": "state-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "newbie"
    assert body["user"]["auth_provider"] == "oidc"

    user = (await db_session.execute(select(User).where(User.oidc_sub == "idp-subject-1"))).scalars().one()
    await db_session.refresh(user)
    assert user.email == "newbie@example.com"
    assert user.hashed_password is None

    profile = api_client.get(
        PROFILE_URL, headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert profile.status_code == 200
    assert profile.json()["username"] == "newbie"

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "LOGIN"))
    ).scalars().one()
    await db_session.refresh(audit)
    assert audit.status == "success"
    assert audit.details == {"method": "oidc"}
    assert audit.user_id == user.id


@pytest.mark.asyncio
async def test_should_propagate_http_error_when_auto_provisioning_is_disabled(
    api_client, db_session, seeded_db, monkeypatch
):
    await _configure_oidc(db_session, oidc_auto_provision=False)
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("verifier-1", "http://testserver/oidc-callback"))
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(oidc_service, "exchange_code", AsyncMock(return_value={"id_token": "t"}))
    monkeypatch.setattr(
        oidc_service,
        "obtain_claims",
        AsyncMock(return_value={"sub": "unknown-sub", "email": "stranger@example.com"}),
    )

    response = api_client.post(CALLBACK_URL, json={"code": "auth-code", "state": "state-2"})

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Your account is not registered in Linguard and automatic provisioning is disabled."
    )


@pytest.mark.asyncio
async def test_should_reuse_existing_oidc_user_when_callback_is_repeated(
    api_client, db_session, seeded_db, monkeypatch
):
    await _configure_oidc(db_session)
    user = User(
        username="returning",
        email="returning@example.com",
        hashed_password=None,
        role="standard",
        auth_provider="oidc",
        oidc_sub="returning-sub",
    )
    db_session.add(user)
    await db_session.commit()

    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("verifier", "http://testserver/oidc-callback"))
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(oidc_service, "exchange_code", AsyncMock(return_value={"id_token": "t"}))
    monkeypatch.setattr(
        oidc_service,
        "obtain_claims",
        AsyncMock(return_value={"sub": "returning-sub", "email": "returning@example.com"}),
    )

    response = api_client.post(CALLBACK_URL, json={"code": "c", "state": "s"})

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id
    users = (await db_session.execute(select(User))).scalars().all()
    assert len(users) == 3  # admin, bob, returning


# ---------------------------------------------------------------------------
# POST /oidc/test
# ---------------------------------------------------------------------------

TEST_PAYLOAD = {
    "discovery_url": "https://authentik.example.com/.well-known/openid-configuration",
    "client_id": "linguard-client",
    "client_secret": "s3cret",
}


@pytest.mark.asyncio
async def test_should_validate_configuration_when_admin_tests_oidc(auth_client, monkeypatch):
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))

    response = auth_client.post(TEST_URL, json=TEST_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["provider_name"] == "Authentik"
    assert "Discovery document valid for Authentik" in body["message"]


@pytest.mark.asyncio
async def test_should_report_failure_when_provider_is_unreachable(auth_client, monkeypatch):
    from app.services.oidc_service import OIDCError

    monkeypatch.setattr(
        oidc_service, "get_discovery", AsyncMock(side_effect=OIDCError("Could not reach discovery URL"))
    )

    response = auth_client.post(TEST_URL, json=TEST_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "provider_name": None,
        "message": "Could not reach discovery URL",
    }


@pytest.mark.asyncio
async def test_should_list_missing_fields_when_discovery_document_is_incomplete(auth_client, monkeypatch):
    monkeypatch.setattr(
        oidc_service,
        "get_discovery",
        AsyncMock(return_value={"issuer": "https://idp.example.com"}),
    )

    response = auth_client.post(TEST_URL, json=TEST_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == (
        "Discovery document is missing: authorization_endpoint, token_endpoint, jwks_uri"
    )


@pytest.mark.asyncio
async def test_should_deny_oidc_test_when_requester_is_standard_user(user_client):
    response = user_client.post(TEST_URL, json=TEST_PAYLOAD)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_should_reject_oidc_test_when_payload_is_incomplete(auth_client):
    response = auth_client.post(TEST_URL, json={"discovery_url": "https://idp.example.com"})

    assert response.status_code == 422
    assert set(response.json()["errors"]) == {"body.client_id", "body.client_secret"}
