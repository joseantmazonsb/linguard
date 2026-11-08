"""Tests for OIDCService: discovery, PKCE flow, token validation and provisioning."""

import asyncio
import base64
import hashlib
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwk, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.services.oidc_service as oidc_module
from app.core.database import Base
from app.core.security import auth_generations, get_password_hash, oidc_configuration_fingerprint
from app.models.settings import GlobalSettings
from app.models.user import User
from app.services.oidc_service import (
    DISCOVERY_TTL_SECONDS,
    FLOW_TTL_SECONDS,
    OIDCError,
    OIDCService,
)

ISSUER = "https://idp.example.com"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"

DISCOVERY = {
    "issuer": ISSUER,
    "authorization_endpoint": f"{ISSUER}/authorize",
    "token_endpoint": f"{ISSUER}/token",
    "jwks_uri": f"{ISSUER}/jwks",
    "userinfo_endpoint": f"{ISSUER}/userinfo",
}


def oidc_settings(**overrides):
    values = {
        "oidc_discovery_url": DISCOVERY_URL,
        "oidc_client_id": "linguard-client",
        "oidc_client_secret": "s3cret",
        "oidc_scopes": "openid email profile",
        "oidc_auto_provision": True,
        "oidc_admin_groups": "",
        "secret_key": "test-secret",
        "setup_completed": True,
        "setup_current_step": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=MagicMock(), response=MagicMock())


def patch_http(get=None, post=None):
    """Patch httpx.AsyncClient used by oidc_service."""
    client = MagicMock()
    for verb, result in (("get", get), ("post", post)):
        if isinstance(result, Exception):
            setattr(client, verb, AsyncMock(side_effect=result))
        else:
            setattr(client, verb, AsyncMock(return_value=result or FakeResponse()))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch.object(oidc_module.httpx, "AsyncClient", return_value=cm), client


@pytest.fixture
def service():
    return OIDCService()


# ----------------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------------


async def test_should_cache_discovery_document_when_fetched(service):
    patcher, client = patch_http(get=FakeResponse(200, DISCOVERY))

    with patcher:
        first = await service.get_discovery(DISCOVERY_URL)
        second = await service.get_discovery(DISCOVERY_URL)

    assert first == DISCOVERY
    assert second == DISCOVERY
    assert client.get.await_count == 1


async def test_should_refetch_discovery_when_forced(service):
    patcher, client = patch_http(get=FakeResponse(200, DISCOVERY))

    with patcher:
        await service.get_discovery(DISCOVERY_URL)
        await service.get_discovery(DISCOVERY_URL, force_refresh=True)

    assert client.get.await_count == 2


async def test_should_refetch_discovery_when_cache_expired(service):
    patcher, client = patch_http(get=FakeResponse(200, DISCOVERY))

    with patcher:
        await service.get_discovery(DISCOVERY_URL)
        doc, fetched_at = service._discovery_cache[DISCOVERY_URL]
        service._discovery_cache[DISCOVERY_URL] = (doc, fetched_at - DISCOVERY_TTL_SECONDS - 1)
        await service.get_discovery(DISCOVERY_URL)

    assert client.get.await_count == 2


async def test_should_raise_oidc_error_when_discovery_url_unreachable(service):
    patcher, _ = patch_http(get=httpx.ConnectError("unreachable"))

    with patcher, pytest.raises(OIDCError, match="Could not reach discovery URL"):
        await service.get_discovery(DISCOVERY_URL)


async def test_should_raise_oidc_error_when_discovery_is_not_json(service):
    patcher, _ = patch_http(get=FakeResponse(200, None))

    with patcher, pytest.raises(OIDCError, match="valid JSON"):
        await service.get_discovery(DISCOVERY_URL)


@pytest.mark.parametrize("missing_field", ["authorization_endpoint", "token_endpoint", "issuer"])
async def test_should_raise_oidc_error_when_discovery_field_missing(service, missing_field):
    doc = dict(DISCOVERY)
    doc.pop(missing_field)
    patcher, _ = patch_http(get=FakeResponse(200, doc))

    with patcher, pytest.raises(OIDCError, match=missing_field):
        await service.get_discovery(DISCOVERY_URL)


async def test_should_not_cache_discovery_when_invalid(service):
    doc = dict(DISCOVERY)
    doc.pop("issuer")
    patcher, _ = patch_http(get=FakeResponse(200, doc))

    with patcher, pytest.raises(OIDCError):
        await service.get_discovery(DISCOVERY_URL)

    assert service._discovery_cache == {}


@pytest.mark.parametrize(
    "discovery, expected",
    [
        ({"issuer": "https://authentik.example.com/application/o/x/"}, "Authentik"),
        ({"issuer": "https://keycloak.local:8443/realms/main"}, "Keycloak"),
        ({}, "Oidc"),
    ],
)
def test_should_derive_provider_name_when_issuer_given(discovery, expected):
    assert OIDCService.provider_name(discovery) == expected


# ----------------------------------------------------------------------------
# PKCE / authorization URL
# ----------------------------------------------------------------------------


def test_should_generate_s256_pkce_pair_when_requested():
    verifier, challenge = OIDCService._pkce_pair()

    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected
    assert 43 <= len(verifier) <= 128
    assert "=" not in challenge


async def test_should_build_authorization_url_when_settings_given(service):
    with patch.object(service, "get_discovery", new=AsyncMock(return_value=DISCOVERY)):
        url = await service.build_authorization_url(
            oidc_settings(), "https://linguard.local/auth/callback"
        )

    assert url.startswith(f"{ISSUER}/authorize?")
    query = url.split("?", 1)[1]
    from urllib.parse import parse_qs

    params = parse_qs(query)
    assert params["response_type"] == ["code"]
    assert params["client_id"] == ["linguard-client"]
    assert params["redirect_uri"] == ["https://linguard.local/auth/callback"]
    assert params["scope"] == ["openid email profile"]
    assert params["code_challenge_method"] == ["S256"]
    state = params["state"][0]
    verifier, redirect_uri, expires_at, binding = service._pending_flows[state]
    assert binding == (oidc_configuration_fingerprint(oidc_settings()), "")
    assert redirect_uri == "https://linguard.local/auth/callback"
    assert expires_at > time.time()
    assert base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode() == params["code_challenge"][0]


async def test_should_use_default_scope_and_ampersand_when_endpoint_has_query(service):
    discovery = dict(DISCOVERY, authorization_endpoint=f"{ISSUER}/authorize?tenant=a")
    with patch.object(service, "get_discovery", new=AsyncMock(return_value=discovery)):
        url = await service.build_authorization_url(
            oidc_settings(oidc_scopes=None), "https://linguard.local/cb"
        )

    assert "?tenant=a&response_type=code" in url
    assert "scope=openid+email+profile" in url or "scope=openid%20email%20profile" in url


async def test_should_propagate_discovery_failure_when_building_authorization_url(service):
    with patch.object(
        service, "get_discovery", new=AsyncMock(side_effect=OIDCError("nope"))
    ), pytest.raises(OIDCError, match="nope"):
        await service.build_authorization_url(oidc_settings(), "https://linguard.local/cb")


def test_should_return_flow_and_consume_it_when_state_known(service):
    service._pending_flows["state-1"] = ("verifier-1", "https://cb", time.time() + FLOW_TTL_SECONDS, ("fingerprint", ""))

    assert service.pop_flow("state-1") == ("verifier-1", "https://cb", ("fingerprint", ""))
    # One-shot: the state cannot be reused
    with pytest.raises(OIDCError, match="Invalid or expired login state"):
        service.pop_flow("state-1")


def test_should_raise_oidc_error_when_state_unknown(service):
    with pytest.raises(OIDCError, match="Invalid or expired login state"):
        service.pop_flow("missing")


def test_should_raise_oidc_error_when_flow_expired(service):
    service._pending_flows["state-2"] = ("v", "https://cb", time.time() - 1, ("fingerprint", ""))

    with pytest.raises(OIDCError, match="Login flow expired"):
        service.pop_flow("state-2")


def test_should_prune_only_expired_flows(service):
    service._pending_flows["fresh"] = ("v", "cb", time.time() + 100)
    service._pending_flows["stale"] = ("v", "cb", time.time() - 100)

    service._prune_flows()

    assert list(service._pending_flows) == ["fresh"]


# ----------------------------------------------------------------------------
# Code exchange and claims
# ----------------------------------------------------------------------------


async def test_should_send_pkce_parameters_when_exchanging_code(service):
    patcher, client = patch_http(post=FakeResponse(200, {"access_token": "at", "id_token": "id"}))
    settings = oidc_settings()

    with patcher:
        tokens = await service.exchange_code(
            settings, DISCOVERY, "code-1", "https://linguard.local/cb", "verifier-1"
        )

    assert tokens == {"access_token": "at", "id_token": "id"}
    call = client.post.await_args
    assert call.args[0] == f"{ISSUER}/token"
    assert call.kwargs["data"] == {
        "grant_type": "authorization_code",
        "code": "code-1",
        "redirect_uri": "https://linguard.local/cb",
        "client_id": "linguard-client",
        "client_secret": "s3cret",
        "code_verifier": "verifier-1",
    }


async def test_should_raise_oidc_error_when_token_endpoint_rejects_code(service):
    patcher, _ = patch_http(post=FakeResponse(400, {"error": "invalid_grant"}, text="invalid_grant"))

    with patcher, pytest.raises(OIDCError, match="rejected the login attempt"):
        await service.exchange_code(oidc_settings(), DISCOVERY, "bad", "cb", "verifier")


async def test_should_raise_oidc_error_when_token_endpoint_unreachable(service):
    patcher, _ = patch_http(post=httpx.ConnectTimeout("timeout"))

    with patcher, pytest.raises(OIDCError, match="Could not reach the identity provider"):
        await service.exchange_code(oidc_settings(), DISCOVERY, "code", "cb", "verifier")


async def test_should_return_none_when_userinfo_not_advertised(service):
    discovery = dict(DISCOVERY)
    discovery.pop("userinfo_endpoint")
    patcher, client = patch_http(get=FakeResponse(200, {"email": "x"}))

    with patcher:
        assert await service.fetch_userinfo(discovery, "at") is None
    client.get.assert_not_awaited()


async def test_should_return_userinfo_claims_when_endpoint_responds(service):
    patcher, client = patch_http(get=FakeResponse(200, {"email": "x@y.z"}))

    with patcher:
        claims = await service.fetch_userinfo(DISCOVERY, "access-token")

    assert claims == {"email": "x@y.z"}
    assert client.get.await_args.args[0] == f"{ISSUER}/userinfo"
    assert client.get.await_args.kwargs["headers"] == {"Authorization": "Bearer access-token"}


async def test_should_return_none_when_userinfo_fails(service):
    for result in (FakeResponse(401, {"error": "invalid_token"}), httpx.ConnectError("down")):
        patcher, _ = patch_http(get=result)
        with patcher:
            assert await service.fetch_userinfo(DISCOVERY, "at") is None


async def test_should_raise_oidc_error_when_jwks_uri_missing(service):
    discovery = dict(DISCOVERY)
    discovery.pop("jwks_uri")

    with pytest.raises(OIDCError, match="jwks_uri"):
        await service.get_jwks(discovery)


async def test_should_return_jwks_document_when_available(service):
    jwks = {"keys": [{"kid": "k1"}]}
    patcher, client = patch_http(get=FakeResponse(200, jwks))

    with patcher:
        assert await service.get_jwks(DISCOVERY) == jwks
    assert client.get.await_args.args[0] == f"{ISSUER}/jwks"


async def test_should_raise_oidc_error_when_jwks_fetch_fails(service):
    patcher, _ = patch_http(get=httpx.ReadTimeout("slow"))

    with patcher, pytest.raises(OIDCError, match="signing keys"):
        await service.get_jwks(DISCOVERY)


# --- real RS256 tokens ------------------------------------------------------


@pytest.fixture(scope="module")
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_jwk = jwk.construct(private_pem, "RS256").to_dict()
    public_jwk.update({"kid": "key-1", "use": "sig", "alg": "RS256"})
    return private_pem, {"keys": [public_jwk]}


def make_id_token(private_pem, claims, kid="key-1"):
    now = int(time.time())
    payload = {"iss": ISSUER, "aud": "linguard-client", "iat": now, "exp": now + 300}
    payload.update(claims)
    return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": kid})


async def test_should_return_claims_when_id_token_is_valid(service, rsa_keypair):
    private_pem, jwks = rsa_keypair
    token = make_id_token(private_pem, {"sub": "abc", "email": "a@b.c"})

    with patch.object(service, "get_jwks", new=AsyncMock(return_value=jwks)):
        claims = await service.validate_id_token(oidc_settings(), DISCOVERY, token)

    assert claims["sub"] == "abc"
    assert claims["email"] == "a@b.c"
    assert claims["iss"] == ISSUER


async def test_should_reject_id_token_without_expiration(service, rsa_keypair):
    private_pem, jwks = rsa_keypair
    token = jwt.encode({"sub": "abc", "iss": ISSUER, "aud": "linguard-client"}, private_pem,
                       algorithm="RS256", headers={"kid": "key-1"})
    with patch.object(service, "get_jwks", new=AsyncMock(return_value=jwks)), pytest.raises(OIDCError):
        await service.validate_id_token(oidc_settings(), DISCOVERY, token)


async def test_should_raise_oidc_error_when_token_is_malformed(service, rsa_keypair):
    _, jwks = rsa_keypair
    with patch.object(service, "get_jwks", new=AsyncMock(return_value=jwks)), \
         pytest.raises(OIDCError, match="malformed"):
        await service.validate_id_token(oidc_settings(), DISCOVERY, "not-a-jwt")


async def test_should_raise_oidc_error_when_signing_key_not_in_jwks(service, rsa_keypair):
    private_pem, jwks = rsa_keypair
    token = make_id_token(private_pem, {"sub": "abc"}, kid="other-kid")

    with patch.object(service, "get_jwks", new=AsyncMock(return_value=jwks)), \
         pytest.raises(OIDCError, match="signing key not found"):
        await service.validate_id_token(oidc_settings(), DISCOVERY, token)


@pytest.mark.parametrize(
    "claims, settings_overrides, discovery_overrides",
    [
        ({"iss": "https://evil.example.com"}, {}, {}),
        ({}, {"oidc_client_id": "someone-else"}, {}),
        ({"exp": int(time.time()) - 3600}, {}, {}),
    ],
    ids=["wrong-issuer", "wrong-audience", "expired"],
)
async def test_should_reject_id_token_when_claim_invalid(
    service, rsa_keypair, claims, settings_overrides, discovery_overrides
):
    private_pem, jwks = rsa_keypair
    token = make_id_token(private_pem, claims)
    discovery = dict(DISCOVERY, **discovery_overrides)

    with patch.object(service, "get_jwks", new=AsyncMock(return_value=jwks)), \
         pytest.raises(OIDCError, match="validation failed"):
        await service.validate_id_token(oidc_settings(**settings_overrides), discovery, token)


async def test_should_merge_userinfo_into_claims_when_obtaining(service, rsa_keypair):
    private_pem, _ = rsa_keypair
    service.validate_id_token = AsyncMock(return_value={"sub": "abc", "email": "id@token"})
    service.fetch_userinfo = AsyncMock(return_value={"sub": "abc", "email": "userinfo@x", "groups": ["admins"]})

    claims = await service.obtain_claims(
        oidc_settings(), DISCOVERY, {"id_token": "t", "access_token": "at"}
    )

    assert claims == {"sub": "abc", "email": "userinfo@x", "groups": ["admins"]}
    service.fetch_userinfo.assert_awaited_once_with(DISCOVERY, "at")


@pytest.mark.parametrize("userinfo", [{"sub": "other", "groups": ["admins"]}, {"email": "x@y"}, {}])
async def test_should_reject_userinfo_with_missing_or_mismatched_subject(service, rsa_keypair, userinfo):
    private_pem, jwks = rsa_keypair
    token = make_id_token(private_pem, {"sub": "abc"})
    with patch.object(service, "get_jwks", new=AsyncMock(return_value=jwks)), \
         patch.object(service, "fetch_userinfo", new=AsyncMock(return_value=userinfo)), \
         pytest.raises(OIDCError, match="subject"):
        await service.obtain_claims(oidc_settings(), DISCOVERY, {"id_token": token})


async def test_should_reject_missing_id_token_subject_before_merging_userinfo(service, rsa_keypair):
    private_pem, jwks = rsa_keypair
    token = make_id_token(private_pem, {})
    with patch.object(service, "get_jwks", new=AsyncMock(return_value=jwks)), \
         patch.object(service, "fetch_userinfo", new=AsyncMock(return_value={"sub": "abc"})), \
         pytest.raises(OIDCError, match="subject"):
        await service.obtain_claims(oidc_settings(), DISCOVERY, {"id_token": token})


async def test_should_keep_id_token_claims_when_userinfo_absent(service):
    service.validate_id_token = AsyncMock(return_value={"sub": "abc"})
    service.fetch_userinfo = AsyncMock(return_value=None)

    claims = await service.obtain_claims(oidc_settings(), DISCOVERY, {"id_token": "t"})

    assert claims == {"sub": "abc"}


async def test_should_not_inherit_verification_for_userinfo_email(service):
    service.validate_id_token = AsyncMock(return_value={"sub": "abc", "email": "old@x", "email_verified": True})
    service.fetch_userinfo = AsyncMock(return_value={"sub": "abc", "email": "new@x"})
    claims = await service.obtain_claims(oidc_settings(), DISCOVERY, {"id_token": "t"})
    assert claims["email"] == "new@x"
    assert claims.get("email_verified") is not True


async def test_should_not_apply_userinfo_verification_to_id_token_email(service):
    service.validate_id_token = AsyncMock(return_value={"sub": "abc", "email": "old@x"})
    service.fetch_userinfo = AsyncMock(return_value={"sub": "abc", "email_verified": True})
    claims = await service.obtain_claims(oidc_settings(), DISCOVERY, {"id_token": "t"})
    assert claims.get("email_verified") is not True


async def test_should_raise_oidc_error_when_id_token_missing(service):
    with pytest.raises(OIDCError, match="did not return an ID token"):
        await service.obtain_claims(oidc_settings(), DISCOVERY, {"access_token": "at"})


# ----------------------------------------------------------------------------
# Role mapping
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "groups_claim, configured, expected",
    [
        ({"groups": ["admins"]}, "admins,ops", "admin"),
        ({"groups": ["users"]}, "admins", "standard"),
        ({"groups": "admins"}, " admins ", "admin"),
        ({"groups": ["admins"]}, "", None),
        ({"groups": []}, "admins", "standard"),
    ],
)
def test_should_map_groups_to_role_when_configured(groups_claim, configured, expected):
    assert OIDCService._role_from_groups(groups_claim, configured) == expected


@pytest.mark.parametrize("groups_claim", [{}, {"groups": None}, {"groups": 123}, {"groups": ["admins", None]}])
def test_should_reject_missing_or_invalid_groups_when_mapping_configured(groups_claim):
    with pytest.raises(OIDCError, match="groups"):
        OIDCService._role_from_groups(groups_claim, "admins")


# ----------------------------------------------------------------------------
# User provisioning
# ----------------------------------------------------------------------------


async def _seed_user(db_session, username, email, **kwargs):
    user = User(
        username=username,
        email=email,
        hashed_password=kwargs.pop("hashed_password", "hashed"),
        role=kwargs.pop("role", "standard"),
        auth_provider=kwargs.pop("auth_provider", "local"),
        oidc_sub=kwargs.pop("oidc_sub", None),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_should_return_existing_user_when_oidc_sub_matches(service, api_db, db_session):
    existing = await _seed_user(db_session, "alice", "alice@x", auth_provider="oidc", oidc_sub="sub-1")

    user = await service.get_or_provision_user(db_session, oidc_settings(), {"sub": "sub-1"})

    assert user.id == existing.id


async def test_should_raise_oidc_error_when_sub_claim_missing(service, api_db, db_session):
    with pytest.raises(OIDCError, match="'sub' claim"):
        await service.get_or_provision_user(db_session, oidc_settings(), {"email": "a@b.c"})


@pytest.mark.parametrize("verified", [True, False, None])
@pytest.mark.parametrize("role", ["admin", "standard"])
@pytest.mark.parametrize("auto_provision", [True, False])
async def test_should_refuse_linking_local_account_by_email(
    service, api_db, db_session, verified, role, auto_provision
):
    local = await _seed_user(db_session, "bob", "bob@x", role=role)

    with pytest.raises((OIDCError, HTTPException)):
        await service.get_or_provision_user(
            db_session, oidc_settings(oidc_auto_provision=auto_provision),
            {"sub": "sub-bob", "email": "bob@x", "email_verified": verified},
        )

    await db_session.refresh(local)
    assert local.auth_provider == "local"
    assert local.oidc_sub is None
    assert local.hashed_password == "hashed"
    assert local.role == role


async def test_should_refuse_relinking_another_oidc_subject_by_email(service, api_db, db_session):
    existing = await _seed_user(db_session, "bob", "bob@x", auth_provider="oidc", oidc_sub="original")
    with pytest.raises((OIDCError, HTTPException)):
        await service.get_or_provision_user(
            db_session, oidc_settings(), {"sub": "different", "email": "bob@x", "email_verified": True}
        )
    await db_session.refresh(existing)
    assert existing.oidc_sub == "original"


@pytest.mark.parametrize(
    "initial_role, groups, configured, expected",
    [
        ("standard", ["admins"], "admins", "admin"),
        ("admin", ["users"], "admins", "standard"),
        ("admin", [], "admins", "standard"),
    ],
)
async def test_should_sync_role_for_existing_oidc_account(
    service, api_db, db_session, initial_role, groups, configured, expected
):
    existing = await _seed_user(
        db_session, "alice", "alice@x", role=initial_role, auth_provider="oidc", oidc_sub="sub-1"
    )
    await _seed_user(db_session, "other-admin", "other@x", role="admin")
    user = await service.get_or_provision_user(
        db_session, oidc_settings(oidc_admin_groups=configured, oidc_auto_provision=False),
        {"sub": "sub-1", "groups": groups},
    )
    await db_session.refresh(existing)
    assert user.id == existing.id
    assert existing.role == expected


@pytest.mark.parametrize("mapping", ["", "  ,  ", None])
@pytest.mark.parametrize("groups_claim", [{}, {"groups": None}, {"groups": []}, {"groups": ["admins"]}])
@pytest.mark.parametrize("provider,role", [("oidc", "admin"), ("oidc", "standard"), ("local", "admin")])
async def test_should_preserve_existing_role_when_admin_mapping_not_configured(
    service, api_db, db_session, mapping, groups_claim, provider, role
):
    existing = await _seed_user(db_session, "alice", "alice@x", role=role, auth_provider=provider, oidc_sub="sub-1")
    user = await service.get_or_provision_user(
        db_session, oidc_settings(oidc_admin_groups=mapping), {"sub": "sub-1", **groups_claim}
    )
    await db_session.refresh(existing)
    assert user.id == existing.id
    assert existing.role == role


async def test_should_provision_standard_user_when_admin_mapping_missing(service, api_db, db_session):
    user = await service.get_or_provision_user(
        db_session, oidc_settings(oidc_admin_groups=""), {"sub": "new-sub", "email": "new@x"}
    )
    assert user.role == "standard"


async def test_should_deny_linked_local_admin_when_group_no_longer_matches(service, api_db, db_session):
    existing = await _seed_user(db_session, "alice", "alice@x", role="admin", oidc_sub="sub-1")
    with pytest.raises(OIDCError, match="admin"):
        await service.get_or_provision_user(
            db_session, oidc_settings(oidc_admin_groups="admins"), {"sub": "sub-1", "groups": []}
        )
    await db_session.refresh(existing)
    assert existing.role == "admin"


@pytest.mark.parametrize("groups", [["users"], []])
async def test_should_deny_login_without_demoting_last_admin(service, api_db, db_session, groups):
    existing = await _seed_user(db_session, "alice", "alice@x", role="admin", auth_provider="oidc", oidc_sub="sub-1")
    with pytest.raises(OIDCError, match="last administrator"):
        await service.get_or_provision_user(db_session, oidc_settings(oidc_admin_groups="admins"),
                                            {"sub": "sub-1", "groups": groups})
    await db_session.refresh(existing)
    assert existing.role == "admin"


async def test_should_not_count_unlinked_local_admin_in_oidc_only_mode(service, api_db, db_session):
    existing = await _seed_user(db_session, "alice", "alice@x", role="admin", auth_provider="oidc", oidc_sub="sub-1")
    await _seed_user(db_session, "local", "local@x", role="admin")
    with pytest.raises(OIDCError, match="last administrator"):
        await service.get_or_provision_user(db_session, oidc_settings(auth_mode="oidc_only", oidc_admin_groups="admins"),
                                            {"sub": "sub-1", "groups": []})
    await db_session.refresh(existing)
    assert existing.role == "admin"


async def test_should_serialize_concurrent_admin_demotions(service, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'demotions.db'}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        async with sessions() as session:
            await _seed_user(session, "alice", "alice@x", role="admin", auth_provider="oidc", oidc_sub="alice")
            await _seed_user(session, "bob", "bob@x", role="admin", auth_provider="oidc", oidc_sub="bob")

        async def demote(subject):
            async with sessions() as session:
                try:
                    await service.get_or_provision_user(session, oidc_settings(oidc_admin_groups="admins"),
                                                        {"sub": subject, "groups": []})
                    await session.commit()
                    return "demoted"
                except OIDCError:
                    await session.rollback()
                    return "denied"

        assert sorted(await asyncio.gather(demote("alice"), demote("bob"))) == ["demoted", "denied"]
        async with sessions() as session:
            admins = (await session.execute(select(User).where(User.role == "admin"))).scalars().all()
            assert len(admins) == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize("groups_claim", [{}, {"groups": None}])
async def test_should_deny_login_without_changing_role_when_groups_missing(service, api_db, db_session, groups_claim):
    existing = await _seed_user(db_session, "alice", "alice@x", role="admin", auth_provider="oidc", oidc_sub="sub-1")
    with pytest.raises(OIDCError, match="groups"):
        await service.get_or_provision_user(db_session, oidc_settings(oidc_admin_groups="admins"),
                                            {"sub": "sub-1", **groups_claim})
    await db_session.refresh(existing)
    assert existing.role == "admin"


async def test_should_securely_link_local_admin_using_password_and_fresh_oidc_flow(service, api_db, db_session):
    local = await _seed_user(db_session, "alice", "alice@x", role="admin", hashed_password=get_password_hash("secret"))
    settings = GlobalSettings(secret_key="test-secret", backup_dir="./b", auth_mode="both", setup_completed=True,
                              oidc_discovery_url=DISCOVERY_URL, oidc_client_id="linguard-client", oidc_client_secret="s3cret",
                              oidc_scopes="openid email profile", oidc_admin_groups="admins")
    db_session.add(settings)
    await db_session.commit()
    token = jwt.encode({"sub": "alice", "auth_method": "local", "exp": 9999999999}, settings.secret_key, algorithm="HS256")
    service._pending_flows["state"] = ("verifier", "https://cb", time.time() + 60, (oidc_configuration_fingerprint(settings), auth_generations(settings)[1]))
    service.get_discovery = AsyncMock(return_value=DISCOVERY)
    service.exchange_code = AsyncMock(return_value={"id_token": "token"})
    service.obtain_claims = AsyncMock(return_value={"sub": "alice-sub", "email": "alice@x", "email_verified": True, "groups": ["admins"]})
    user = await service.link_local_account(db_session, settings, "alice", "secret", "state", "code", token)
    assert user.id == local.id
    assert user.auth_provider == "local"
    assert user.oidc_sub == "alice-sub"
    assert user.role == "admin"
    service.exchange_code.assert_awaited_once_with(settings, DISCOVERY, "code", "https://cb", "verifier")
    with pytest.raises(OIDCError):
        service.pop_flow("state")
    assert (await service.get_or_provision_user(db_session, oidc_settings(oidc_admin_groups="admins"),
                                                {"sub": "alice-sub", "groups": ["admins"]})).id == local.id


@pytest.mark.parametrize("password, email, verified, groups, subject", [
    ("wrong", "alice@x", True, ["admins"], "alice-sub"),
    ("secret", "other@x", True, ["admins"], "alice-sub"),
    ("secret", "alice@x", False, ["admins"], "alice-sub"),
    ("secret", "alice@x", None, ["admins"], "alice-sub"),
    ("secret", "alice@x", True, [], "alice-sub"),
    ("secret", "alice@x", True, None, "alice-sub"),
    ("secret", "alice@x", True, ["admins"], "taken"),
])
async def test_should_refuse_unsafe_local_link(service, api_db, db_session, password, email, verified, groups, subject):
    local = await _seed_user(db_session, "alice", "alice@x", role="admin", hashed_password=get_password_hash("secret"))
    await _seed_user(db_session, "other", "other@x", auth_provider="oidc", oidc_sub="taken")
    settings = GlobalSettings(secret_key="test-secret", backup_dir="./b", auth_mode="both", setup_completed=True,
                              oidc_discovery_url=DISCOVERY_URL, oidc_client_id="linguard-client", oidc_client_secret="s3cret",
                              oidc_scopes="openid email profile", oidc_admin_groups="admins")
    db_session.add(settings)
    await db_session.commit()
    token = jwt.encode({"sub": "alice", "auth_method": "local", "exp": 9999999999}, settings.secret_key, algorithm="HS256")
    service._pending_flows["state"] = ("verifier", "https://cb", time.time() + 60, (oidc_configuration_fingerprint(settings), auth_generations(settings)[1]))
    service.get_discovery = AsyncMock(return_value=DISCOVERY)
    service.exchange_code = AsyncMock(return_value={"id_token": "token"})
    service.obtain_claims = AsyncMock(return_value={"sub": subject, "email": email, "email_verified": verified, "groups": groups})
    with pytest.raises(OIDCError):
        await service.link_local_account(db_session, settings, "alice", password, "state", "code", token)
    await db_session.refresh(local)
    assert local.oidc_sub is None
    assert local.role == "admin"


async def test_should_refuse_unknown_user_when_auto_provision_disabled(service, api_db, db_session):
    with pytest.raises(HTTPException) as excinfo:
        await service.get_or_provision_user(
            db_session,
            oidc_settings(oidc_auto_provision=False),
            {"sub": "new-sub", "email": "new@x"},
        )

    assert excinfo.value.status_code == 403
    assert "automatic provisioning is disabled" in excinfo.value.detail


async def test_should_refuse_provisioning_when_email_missing(service, api_db, db_session):
    with pytest.raises(OIDCError, match="email address"):
        await service.get_or_provision_user(db_session, oidc_settings(), {"sub": "new-sub"})


async def test_should_refuse_provisioning_when_configured_groups_missing(service, api_db, db_session):
    with pytest.raises(OIDCError, match="groups"):
        await service.get_or_provision_user(db_session, oidc_settings(oidc_admin_groups="admins"),
                                            {"sub": "new-sub", "email": "new@x"})
    assert (await db_session.execute(select(User).where(User.oidc_sub == "new-sub"))).scalar_one_or_none() is None


async def test_should_provision_admin_user_when_group_matches(service, api_db, db_session):
    user = await service.get_or_provision_user(
        db_session,
        oidc_settings(oidc_admin_groups="linguard-admins, other"),
        {"sub": "sub-new", "email": "carol@x", "preferred_username": "carol", "groups": ["other"]},
    )

    assert user.username == "carol"
    assert user.email == "carol@x"
    assert user.role == "admin"
    assert user.auth_provider == "oidc"
    assert user.oidc_sub == "sub-new"
    assert user.hashed_password is None

    stored = (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert stored.username == "carol"


async def test_should_provision_standard_user_when_no_group_matches(service, api_db, db_session):
    user = await service.get_or_provision_user(
        db_session,
        oidc_settings(oidc_admin_groups="admins"),
        {"sub": "sub-new", "email": "dave@x", "groups": ["users"]},
    )

    assert user.role == "standard"


async def test_should_suffix_username_when_already_taken(service, api_db, db_session):
    await _seed_user(db_session, "erin", "erin@local")
    await _seed_user(db_session, "erin-2", "erin2@local")

    user = await service.get_or_provision_user(
        db_session,
        oidc_settings(),
        {"sub": "sub-erin", "email": "erin@oidc", "preferred_username": "erin"},
    )

    assert user.username == "erin-3"


async def test_should_derive_username_from_email_when_not_provided(service, api_db, db_session):
    user = await service.get_or_provision_user(
        db_session, oidc_settings(), {"sub": "sub-frank", "email": "frank@corp.example"}
    )

    assert user.username == "frank"


async def test_should_truncate_username_when_preferred_username_too_long(service, api_db, db_session):
    long_name = "u" * 80

    user = await service.get_or_provision_user(
        db_session, oidc_settings(), {"sub": "sub-long", "email": "long@x", "preferred_username": long_name}
    )

    assert user.username == "u" * 50


async def test_should_use_generic_username_when_preferred_username_empty(service, api_db, db_session):
    assert await service._unique_username(db_session, "") == "user"
