"""Tests for the OIDC / Single Sign-On endpoints."""

from unittest.mock import AsyncMock

import pytest
from jose import jwt
from sqlalchemy import select

from app.api.auth import oidc_service
from app.core.security import auth_generations, oidc_configuration_fingerprint
from app.models.audit import AuditLog
from app.models.settings import GlobalSettings
from app.models.user import User

CONFIG_URL = "/api/v1/auth/oidc/config"
LOGIN_URL = "/api/v1/auth/oidc/login"
CALLBACK_URL = "/api/v1/auth/oidc/callback"
TEST_URL = "/api/v1/auth/oidc/test"
PROFILE_URL = "/api/v1/auth/profile"


@pytest.mark.asyncio
async def test_should_revoke_legacy_and_oidc_tokens_when_local_only_is_reenabled(api_client, db_session, seeded_db):
    from app.core.security import oidc_configuration_fingerprint

    settings = await _configure_oidc(db_session)
    local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    oidc = jwt.encode({"sub": "admin", "auth_method": "oidc", "oidc_config": oidc_configuration_fingerprint(settings), "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    legacy = jwt.encode({"sub": "admin", "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    headers = lambda token: {"Authorization": f"Bearer {token}"}
    assert api_client.put("/api/v1/settings/global", headers=headers(local), json={"auth_mode": "local_only"}).status_code == 200
    assert api_client.get(PROFILE_URL, headers=headers(legacy)).status_code == 401
    assert api_client.put("/api/v1/settings/global", headers=headers(local), json={"auth_mode": "both"}).status_code == 200
    assert api_client.get(PROFILE_URL, headers=headers(oidc)).status_code == 401
    assert api_client.get(PROFILE_URL, headers=headers(legacy)).status_code == 401


@pytest.mark.asyncio
async def test_should_reject_ambiguous_legacy_token_for_existing_local_only_deployment(api_client, db_session, seeded_db):
    settings = await _configure_oidc(db_session, auth_mode="local_only")
    legacy = jwt.encode({"sub": "admin", "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    assert api_client.get(PROFILE_URL, headers={"Authorization": f"Bearer {legacy}"}).status_code == 401
    local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    assert api_client.put("/api/v1/settings/global", headers={"Authorization": f"Bearer {local}"}, json={"auth_mode": "both"}).status_code == 200
    assert api_client.get(PROFILE_URL, headers={"Authorization": f"Bearer {legacy}"}).status_code == 401


@pytest.mark.asyncio
async def test_should_reject_flow_started_before_provider_changes(api_client, db_session, seeded_db, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    settings = await _configure_oidc(db_session)
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(oidc_service, "exchange_code", AsyncMock(return_value={"id_token": "t"}))
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value={"sub": "new-sub", "email": "new@example.com"}))
    login = api_client.get(LOGIN_URL)
    state = parse_qs(urlparse(login.json()["authorization_url"]).query)["state"][0]
    settings.oidc_discovery_url = "https://different.example/discovery"
    await db_session.commit()
    response = api_client.post(CALLBACK_URL, json={"code": "c", "state": state})
    assert response.status_code == 401
    assert (await db_session.execute(select(User).where(User.oidc_sub == "new-sub"))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_should_reject_flow_after_oidc_configuration_is_changed_back(api_client, db_session, seeded_db, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    await _configure_oidc(db_session, oidc_admin_groups="admins")
    local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {local}"}
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    state = parse_qs(urlparse(api_client.get(LOGIN_URL).json()["authorization_url"]).query)["state"][0]
    assert api_client.put("/api/v1/settings/global", headers=headers, json={"oidc_admin_groups": "other"}).status_code == 200
    assert api_client.put("/api/v1/settings/global", headers=headers, json={"oidc_admin_groups": "admins"}).status_code == 200
    assert api_client.post(CALLBACK_URL, json={"code": "c", "state": state}).status_code == 401


@pytest.mark.asyncio
async def test_should_not_provision_when_provider_changes_during_exchange(api_client, db_session, seeded_db, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    settings = await _configure_oidc(db_session)
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    async def exchange(*args):
        settings.oidc_discovery_url = "https://different.example/discovery"
        await db_session.commit()
        return {"id_token": "t"}
    monkeypatch.setattr(oidc_service, "exchange_code", exchange)
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value={"sub": "new-sub", "email": "new@example.com"}))
    state = parse_qs(urlparse(api_client.get(LOGIN_URL).json()["authorization_url"]).query)["state"][0]
    response = api_client.post(CALLBACK_URL, json={"code": "c", "state": state})
    assert response.status_code == 401
    assert (await db_session.execute(select(User).where(User.oidc_sub == "new-sub"))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_should_not_provision_when_local_only_temporarily_enabled_during_exchange(api_client, db_session, seeded_db, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    from starlette.testclient import TestClient
    from app.main import app

    await _configure_oidc(db_session)
    local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {local}"}
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    async def exchange(*args):
        client = TestClient(app, raise_server_exceptions=False)
        assert client.put("/api/v1/settings/global", headers=headers, json={"auth_mode": "local_only"}).status_code == 200
        assert client.put("/api/v1/settings/global", headers=headers, json={"auth_mode": "both"}).status_code == 200
        return {"id_token": "t"}
    monkeypatch.setattr(oidc_service, "exchange_code", exchange)
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value={"sub": "new-sub", "email": "new@example.com"}))
    state = parse_qs(urlparse(api_client.get(LOGIN_URL).json()["authorization_url"]).query)["state"][0]
    assert api_client.post(CALLBACK_URL, json={"code": "c", "state": state}).status_code == 401
    assert (await db_session.execute(select(User).where(User.oidc_sub == "new-sub"))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_should_not_link_when_provider_changes_during_exchange(api_client, db_session, seeded_db, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    token = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    async def exchange(*args):
        settings.oidc_discovery_url = "https://different.example/discovery"
        await db_session.commit()
        return {"id_token": "t"}
    monkeypatch.setattr(oidc_service, "exchange_code", exchange)
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value={"sub": "linked", "email": "admin@example.com", "email_verified": True, "groups": ["admins"]}))
    state = parse_qs(urlparse(api_client.get(LOGIN_URL).json()["authorization_url"]).query)["state"][0]
    response = api_client.post("/api/v1/auth/oidc/link", headers={"Authorization": f"Bearer {token}"}, json={"code": "c", "state": state, "password": "admin123"})
    assert response.status_code == 401
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    await db_session.refresh(admin)
    assert admin.oidc_sub is None


@pytest.mark.asyncio
async def test_should_enable_oidc_only_after_successful_oidc_admin_login(api_client, db_session, seeded_db, monkeypatch):
    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("verifier", "http://testserver/oidc-callback", (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])))
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(oidc_service, "exchange_code", AsyncMock(return_value={"id_token": "t"}))
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value={
        "sub": "sso-admin", "email": "sso@example.com", "groups": ["admins"]
    }))
    login = api_client.post(CALLBACK_URL, json={"code": "c", "state": "s"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = api_client.put("/api/v1/settings/global", headers=headers, json={"auth_mode": "oidc_only"})
    assert response.status_code == 200
    assert response.json()["auth_mode"] == "oidc_only"
    assert api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).status_code == 403


@pytest.mark.asyncio
async def test_should_link_local_admin_only_after_password_and_verified_oidc_identity(auth_client, db_session, monkeypatch):
    settings = await _configure_oidc(db_session, oidc_admin_groups="admins", oidc_auto_provision=False)
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("verifier", "http://testserver/oidc-callback", (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])))
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(oidc_service, "exchange_code", AsyncMock(return_value={"id_token": "t"}))
    claims = {"sub": "linked-admin", "email": "admin@example.com", "email_verified": True, "groups": ["admins"]}
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value=claims))
    payload = {"code": "c", "state": "s", "password": "wrong"}
    assert auth_client.post("/api/v1/auth/oidc/link", json=payload).status_code == 401
    payload["password"] = "admin123"
    claims["email_verified"] = False
    assert auth_client.post("/api/v1/auth/oidc/link", json=payload).status_code == 401
    claims["email_verified"] = True
    assert auth_client.post("/api/v1/auth/oidc/link", json=payload).status_code == 200
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    await db_session.refresh(admin)
    assert admin.oidc_sub == "linked-admin"
    login = auth_client.post(CALLBACK_URL, json={"code": "c", "state": "s"})
    assert login.status_code == 200
    response = auth_client.put("/api/v1/settings/global", headers={"Authorization": f"Bearer {login.json()['access_token']}"}, json={"auth_mode": "oidc_only"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_should_reject_stale_oidc_session_after_configuration_changes(api_client, db_session, seeded_db, monkeypatch):
    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("v", "http://testserver/oidc-callback", (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])))
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(oidc_service, "exchange_code", AsyncMock(return_value={"id_token": "t"}))
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value={"sub": "sso", "email": "sso@example.com", "groups": ["admins"]}))
    login = api_client.post(CALLBACK_URL, json={"code": "c", "state": "s"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert api_client.put("/api/v1/settings/global", headers=headers, json={"oidc_admin_groups": "other"}).status_code == 200
    assert api_client.get(PROFILE_URL, headers=headers).status_code == 401
    assert api_client.put("/api/v1/settings/global", headers=headers, json={"auth_mode": "oidc_only"}).status_code == 401
    await db_session.refresh(settings)
    fresh_login = api_client.post(CALLBACK_URL, json={"code": "c", "state": "s"})
    assert fresh_login.status_code == 200
    fresh_headers = {"Authorization": f"Bearer {fresh_login.json()['access_token']}"}
    assert api_client.get(PROFILE_URL, headers=fresh_headers).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("oidc_discovery_url", "https://other.example.com/discovery"),
    ("oidc_client_id", "other-client"),
    ("oidc_client_secret", "other-secret"),
    ("oidc_scopes", "openid"),
    ("oidc_admin_groups", "other-admins"),
])
async def test_should_revalidate_oidc_fingerprint_on_each_request(api_client, db_session, seeded_db, field, value):
    from app.api.settings import oidc_configuration_fingerprint

    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    token = jwt.encode({"sub": "admin", "auth_method": "oidc", "exp": 9999999999,
                        "oidc_config": oidc_configuration_fingerprint(settings)}, settings.secret_key, algorithm=settings.algorithm)
    headers = {"Authorization": f"Bearer {token}"}
    assert api_client.get(PROFILE_URL, headers=headers).status_code == 200
    setattr(settings, field, value)
    await db_session.commit()
    assert api_client.get(PROFILE_URL, headers=headers).status_code == 401


@pytest.mark.asyncio
async def test_should_not_revive_oidc_session_after_configuration_is_restored(api_client, auth_client, db_session):
    from app.api.settings import oidc_configuration_fingerprint

    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    token = jwt.encode({"sub": "admin", "auth_method": "oidc", "exp": 9999999999,
                        "oidc_config": oidc_configuration_fingerprint(settings)}, settings.secret_key, algorithm=settings.algorithm)
    headers = {"Authorization": f"Bearer {token}"}
    assert api_client.get(PROFILE_URL, headers=headers).status_code == 200
    local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    local_headers = {"Authorization": f"Bearer {local}"}
    assert auth_client.put("/api/v1/settings/global", headers=local_headers, json={"oidc_admin_groups": "other"}).status_code == 200
    assert auth_client.put("/api/v1/settings/global", headers=local_headers, json={"oidc_admin_groups": "admins"}).status_code == 200
    assert api_client.get(PROFILE_URL, headers=headers).status_code == 401


@pytest.mark.asyncio
async def test_should_reject_missing_or_malformed_oidc_fingerprints(api_client, db_session, seeded_db):
    settings = await _configure_oidc(db_session)
    for fingerprint in (None, "", ["invalid"], "non-ascii-\u00e9"):
        token = jwt.encode({"sub": "admin", "auth_method": "oidc", "oidc_config": fingerprint,
                            "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
        assert api_client.get(PROFILE_URL, headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.asyncio
async def test_should_revoke_ambiguous_legacy_tokens_after_oidc_configuration_change(api_client, auth_client, db_session):
    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    legacy = jwt.encode({"sub": "admin", "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    headers = lambda token: {"Authorization": f"Bearer {token}"}
    assert api_client.get(PROFILE_URL, headers=headers(legacy)).status_code == 200
    assert auth_client.put("/api/v1/settings/global", headers=headers(local), json={"oidc_admin_groups": "other"}).status_code == 200
    assert api_client.get(PROFILE_URL, headers=headers(legacy)).status_code == 401
    assert api_client.get(PROFILE_URL, headers=headers(local)).status_code == 200


@pytest.mark.asyncio
async def test_should_keep_sessions_when_oidc_settings_are_unchanged(api_client, db_session, seeded_db):
    from app.api.settings import oidc_configuration_fingerprint

    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    token = jwt.encode({"sub": "admin", "auth_method": "oidc", "exp": 9999999999,
                        "oidc_config": oidc_configuration_fingerprint(settings)}, settings.secret_key, algorithm=settings.algorithm)
    headers = {"Authorization": f"Bearer {token}"}
    assert api_client.put("/api/v1/settings/global", headers=headers, json={"oidc_admin_groups": "admins"}).status_code == 200
    assert api_client.get(PROFILE_URL, headers=headers).status_code == 200


@pytest.mark.asyncio
async def test_should_revalidate_websocket_sessions_after_oidc_configuration_change(api_client, auth_client, db_session):
    from app.api.settings import oidc_configuration_fingerprint
    from app.api.ws import authenticate
    from jose import JWTError

    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    token = jwt.encode({"sub": "admin", "auth_method": "oidc", "exp": 9999999999,
                        "oidc_config": oidc_configuration_fingerprint(settings)}, settings.secret_key, algorithm=settings.algorithm)
    assert (await authenticate(token))[1] is not None
    assert auth_client.put("/api/v1/settings/global", json={"oidc_admin_groups": "other"}).status_code == 200
    with pytest.raises(JWTError):
        await authenticate(token)


@pytest.mark.asyncio
async def test_should_permanently_revoke_local_sessions_on_oidc_only_transition(api_client, db_session, seeded_db, monkeypatch):
    from app.api.ws import authenticate
    from jose import JWTError

    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    admin.oidc_sub = "linked-admin"
    await db_session.commit()
    local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    legacy = jwt.encode({"sub": "admin", "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("v", "http://testserver/oidc-callback", (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])))
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(oidc_service, "exchange_code", AsyncMock(return_value={"id_token": "t"}))
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value={"sub": "linked-admin", "email": "admin@example.com", "groups": ["admins"]}))
    oidc = api_client.post(CALLBACK_URL, json={"code": "c", "state": "s"}).json()["access_token"]
    headers = lambda token: {"Authorization": f"Bearer {token}"}
    original_key = settings.secret_key
    assert api_client.put("/api/v1/settings/global", headers=headers(oidc), json={"auth_mode": "oidc_only", "secret_key": original_key}).status_code == 200
    assert api_client.get(PROFILE_URL, headers=headers(oidc)).status_code == 200
    assert api_client.put("/api/v1/settings/global", headers=headers(oidc), json={"auth_mode": "both", "secret_key": original_key}).status_code == 200
    for token in (local, legacy):
        assert api_client.get(PROFILE_URL, headers=headers(token)).status_code == 401
        with pytest.raises(JWTError):
            await authenticate(token)
    new_local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    assert api_client.get(PROFILE_URL, headers=headers(new_local)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("secret_key", "new-signing-secret"), ("algorithm", "HS384")])
async def test_should_reject_signing_changes_when_enabling_oidc_only(api_client, db_session, seeded_db, field, value):
    from app.api.settings import oidc_configuration_fingerprint

    settings = await _configure_oidc(db_session)
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    admin.oidc_sub = "admin-sub"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "auth_method": "oidc", "exp": 9999999999,
                        "oidc_config": oidc_configuration_fingerprint(settings)}, settings.secret_key, algorithm=settings.algorithm)
    headers = {"Authorization": f"Bearer {token}"}
    response = api_client.put("/api/v1/settings/global", headers=headers, json={"auth_mode": "oidc_only", field: value})
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert settings.auth_mode == "both"
    assert api_client.get(PROFILE_URL, headers=headers).status_code == 200


@pytest.mark.asyncio
async def test_should_not_enable_oidc_only_with_local_session_carrying_fingerprint(api_client, db_session, seeded_db):
    from app.api.settings import oidc_configuration_fingerprint

    settings = await _configure_oidc(db_session)
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    admin.oidc_sub = "admin-sub"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "auth_method": "local", "exp": 9999999999,
                        "oidc_config": oidc_configuration_fingerprint(settings)}, settings.secret_key, algorithm=settings.algorithm)
    response = api_client.put("/api/v1/settings/global", headers={"Authorization": f"Bearer {token}"}, json={"auth_mode": "oidc_only"})
    assert response.status_code == 400

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


@pytest.mark.asyncio
async def test_should_enforce_authentication_method_after_mode_changes(api_client, db_session, seeded_db, monkeypatch):
    settings = await _configure_oidc(db_session, oidc_admin_groups="admins")
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    admin.oidc_sub = "linked-admin"
    await db_session.commit()
    local = api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    assert jwt.decode(local, settings.secret_key, algorithms=[settings.algorithm])["auth_method"] == "local"
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("v", "http://testserver/oidc-callback", (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])))
    monkeypatch.setattr(oidc_service, "get_discovery", AsyncMock(return_value=DISCOVERY))
    monkeypatch.setattr(oidc_service, "exchange_code", AsyncMock(return_value={"id_token": "t"}))
    monkeypatch.setattr(oidc_service, "obtain_claims", AsyncMock(return_value={"sub": "linked-admin", "email": "admin@example.com", "groups": ["admins"]}))
    oidc = api_client.post(CALLBACK_URL, json={"code": "c", "state": "s"}).json()["access_token"]
    claims = jwt.decode(oidc, settings.secret_key, algorithms=[settings.algorithm])
    assert claims["auth_method"] == "oidc"
    legacy_oidc = jwt.encode({k: v for k, v in claims.items() if k != "auth_method"}, settings.secret_key, algorithm=settings.algorithm)
    legacy = jwt.encode({"sub": "admin", "exp": claims["exp"]}, settings.secret_key, algorithm=settings.algorithm)
    headers = lambda token: {"Authorization": f"Bearer {token}"}
    for token in (local, oidc, legacy, legacy_oidc):
        assert api_client.get(PROFILE_URL, headers=headers(token)).status_code == 200
    for method in (None, "unknown", ["oidc"]):
        invalid = jwt.encode({**claims, "auth_method": method}, settings.secret_key, algorithm=settings.algorithm)
        assert api_client.get(PROFILE_URL, headers=headers(invalid)).status_code == 401
    local_with_fingerprint = jwt.encode({**claims, "auth_method": "local"}, settings.secret_key, algorithm=settings.algorithm)
    assert api_client.put("/api/v1/settings/global", headers=headers(oidc), json={"auth_mode": "oidc_only"}).status_code == 200
    for token in (local, legacy, local_with_fingerprint):
        assert api_client.get(PROFILE_URL, headers=headers(token)).status_code == 401
        assert api_client.get(f"/api/v1/logs/download?token={token}").status_code == 401
    for token in (oidc, legacy_oidc):
        assert api_client.get(PROFILE_URL, headers=headers(token)).status_code == 200
    settings.auth_mode = "local_only"
    await db_session.commit()
    assert api_client.get(PROFILE_URL, headers=headers(oidc)).status_code == 401
    assert api_client.get(PROFILE_URL, headers=headers(legacy_oidc)).status_code == 401
    assert api_client.get(PROFILE_URL, headers=headers(local)).status_code == 401
    assert api_client.get(PROFILE_URL, headers=headers(legacy)).status_code == 401
    settings.auth_mode = "invalid"
    await db_session.commit()
    assert api_client.get(PROFILE_URL, headers=headers(local)).status_code == 401
    assert api_client.get(PROFILE_URL, headers=headers(oidc)).status_code == 401


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
    settings = await _configure_oidc(db_session)
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("verifier-1", "http://testserver/oidc-callback", (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])))
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
    settings = await _configure_oidc(db_session, oidc_auto_provision=False)
    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("verifier-1", "http://testserver/oidc-callback", (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])))
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
    settings = await _configure_oidc(db_session)
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

    monkeypatch.setattr(oidc_service, "pop_flow", lambda state: ("verifier", "http://testserver/oidc-callback", (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])))
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
