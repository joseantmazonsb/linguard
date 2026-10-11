"""Unit tests for the OIDC service (discovery, PKCE, provisioning, role mapping)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.services.oidc_service import FLOW_TTL_SECONDS, OIDCError, OIDCService


@pytest.fixture
def service():
    return OIDCService()


@pytest.fixture
def mock_db():
    """AsyncSession mock whose execute() returns a fresh result each call."""
    db = MagicMock()
    results = []

    def add_result(value):
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        results.append(result)
        return result

    db.execute = AsyncMock(side_effect=lambda *_: add_result(None))
    db._add_result = add_result  # helper for tests to queue specific results
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def make_settings(**overrides):
    settings = MagicMock()
    settings.oidc_discovery_url = "https://idp.example.com/.well-known/openid-configuration"
    settings.oidc_client_id = "linguard"
    settings.oidc_client_secret = "sekrit"
    settings.oidc_scopes = "openid email profile"
    settings.oidc_auto_provision = True
    settings.oidc_admin_groups = "linguard-admins"
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


DISCOVERY = {
    "issuer": "https://idp.example.com/application/o/linguard",
    "authorization_endpoint": "https://idp.example.com/authorize",
    "token_endpoint": "https://idp.example.com/token",
    "jwks_uri": "https://idp.example.com/jwks",
    "userinfo_endpoint": "https://idp.example.com/userinfo",
}


# ---------------------------------------------------------------------------
# PKCE + state flow
# ---------------------------------------------------------------------------


def test_pkce_pair_shape(service):
    verifier, challenge = service._pkce_pair()
    assert 43 <= len(verifier) <= 128
    # S256 challenge is base64url without padding
    assert "=" not in challenge
    import base64
    import hashlib

    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected


@pytest.mark.asyncio
async def test_authorization_url_contains_pkce_and_state(service):
    with patch.object(OIDCService, "get_discovery", AsyncMock(return_value=DISCOVERY)):
        url = await service.build_authorization_url(make_settings(), "http://localhost:5173/oidc-callback")

    assert url.startswith(DISCOVERY["authorization_endpoint"])
    assert "response_type=code" in url
    assert "client_id=linguard" in url
    assert "code_challenge_method=S256" in url
    assert "state=" in url


@pytest.mark.asyncio
async def test_pop_flow_roundtrip(service):
    with patch.object(OIDCService, "get_discovery", AsyncMock(return_value=DISCOVERY)):
        await service.build_authorization_url(make_settings(), "http://localhost:5173/oidc-callback")

    assert len(service._pending_flows) == 1
    state = next(iter(service._pending_flows))
    verifier, redirect_uri = service.pop_flow(state)
    assert redirect_uri == "http://localhost:5173/oidc-callback"
    assert len(verifier) >= 43
    # Flows are single-use
    with pytest.raises(OIDCError):
        service.pop_flow(state)


def test_pop_flow_unknown_state(service):
    with pytest.raises(OIDCError):
        service.pop_flow("does-not-exist")


def test_pop_flow_expired_state(service):
    import time

    service._pending_flows["expired"] = ("verifier", "http://x/cb", time.time() - 1)
    with pytest.raises(OIDCError):
        service.pop_flow("expired")


def test_flow_ttl_is_sane():
    assert 60 <= FLOW_TTL_SECONDS <= 900


# ---------------------------------------------------------------------------
# Provider name
# ---------------------------------------------------------------------------


def test_provider_name_from_issuer(service):
    assert service.provider_name(DISCOVERY) == "Idp"


# ---------------------------------------------------------------------------
# Role mapping
# ---------------------------------------------------------------------------


def test_role_from_groups_matching(service):
    claims = {"groups": ["users", "linguard-admins"]}
    assert service._role_from_groups(claims, "linguard-admins") == "admin"


def test_role_from_groups_no_match(service):
    claims = {"groups": ["users"]}
    assert service._role_from_groups(claims, "linguard-admins") == "standard"


def test_role_from_groups_no_groups_claim(service):
    assert service._role_from_groups({}, "linguard-admins") == "standard"


def test_role_from_groups_no_configured_groups(service):
    claims = {"groups": ["anything"]}
    assert service._role_from_groups(claims, "") == "standard"


def test_role_from_groups_single_string_claim(service):
    claims = {"groups": "linguard-admins"}
    assert service._role_from_groups(claims, "linguard-admins") == "admin"


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provision_returns_existing_user_by_sub(service, mock_db):
    existing = User(username="alice", email="alice@example.com", role="standard", auth_provider="oidc", oidc_sub="sub-1")

    async def execute_side_effect(*_):
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    user = await service.get_or_provision_user(mock_db, make_settings(), {"sub": "sub-1"})
    assert user is existing
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_provision_links_by_email(service, mock_db):
    local_user = User(username="admin", email="alice@example.com", role="admin", auth_provider="local")

    call_count = {"n": 0}

    def execute_side_effect(*_):
        call_count["n"] += 1
        result = MagicMock()
        result.scalar_one_or_none.return_value = local_user if call_count["n"] == 2 else None
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    user = await service.get_or_provision_user(mock_db, make_settings(), {"sub": "sub-2", "email": "alice@example.com"})
    assert user is local_user
    assert user.auth_provider == "oidc"
    assert user.oidc_sub == "sub-2"
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_provision_creates_new_user_standard(service, mock_db):
    def execute_side_effect(*_):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    user = await service.get_or_provision_user(
        mock_db,
        make_settings(),
        {"sub": "sub-3", "email": "bob@example.com", "preferred_username": "bob", "groups": ["users"]},
    )
    assert user.username == "bob"
    assert user.role == "standard"
    assert user.auth_provider == "oidc"
    assert user.oidc_sub == "sub-3"
    assert user.hashed_password is None
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_provision_creates_new_user_admin_via_groups(service, mock_db):
    def execute_side_effect(*_):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    user = await service.get_or_provision_user(
        mock_db,
        make_settings(),
        {"sub": "sub-4", "email": "carol@example.com", "preferred_username": "carol", "groups": ["linguard-admins"]},
    )
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_provision_disabled_raises_403(service, mock_db):
    from fastapi import HTTPException

    def execute_side_effect(*_):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_or_provision_user(
            mock_db, make_settings(oidc_auto_provision=False), {"sub": "sub-5", "email": "dave@example.com"}
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_provision_requires_sub(service, mock_db):
    with pytest.raises(OIDCError):
        await service.get_or_provision_user(mock_db, make_settings(), {"email": "x@example.com"})


@pytest.mark.asyncio
async def test_unique_username_suffix(service, mock_db):
    taken = User(username="bob", email="bob@example.com")

    def execute_side_effect(*_):
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [taken, None]  # first taken, second free
        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)
    username = await service._unique_username(mock_db, "bob")
    assert username == "bob-2"
