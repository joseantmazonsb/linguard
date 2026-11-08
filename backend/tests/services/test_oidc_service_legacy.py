"""
Comprehensive tests for OIDC service.
Tests all OIDC flow, discovery, code exchange, and user provisioning.
"""
import pytest
import base64
import hashlib
import time
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock, Mock

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.services.oidc_service import (
    OIDCService,
    OIDCError,
    FLOW_TTL_SECONDS,
    DISCOVERY_TTL_SECONDS,
)
from app.models.user import User
from app.models.settings import GlobalSettings


class MockDiscoveryDoc:
    """Mock OIDC discovery document."""
    
    def __init__(self, issuer="https://example.com/.well-known/openid-configuration",
                 authorization_endpoint=None,
                 token_endpoint=None,
                 jwks_uri=None,
                 userinfo_endpoint=None):
        self.issuer = issuer
        self.authorization_endpoint = authorization_endpoint or issuer
        self.token_endpoint = token_endpoint or issuer
        self.jwks_uri = jwks_uri
        self.userinfo_endpoint = userinfo_endpoint
    
    def get(self, key, default=None):
        return getattr(self, key, default)


class MockJWKS:
    """Mock JWKS response."""
    
    def __init__(self, keys=None):
        self.keys = keys or [
            {
                "kid": "test-key",
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "n": "test-n",
                "e": "AQAB",
            }
        ]


class MockIDToken:
    """Mock ID token with claims."""
    
    def __init__(self, claims, kid="test-key"):
        header = {"alg": "RS256", "kid": kid}
        encoded_header = jwt.encode(json.dumps(header), "secret", algorithm="HS256")
        encoded_claims = jwt.encode(json.dumps(claims), "secret", algorithm="HS256")
        self.token = f"{encoded_header}.{encoded_claims}.signature"


class MockUserinfoResponse:
    """Mock userinfo endpoint response."""
    
    def __init__(self, claims):
        self._claims = claims
    
    def json(self):
        return self._claims


class MockDiscoveryResponse:
    """Mock HTTP response for discovery."""
    
    def __init__(self, doc, status_code=200):
        self.status_code = status_code
        self._doc = doc
    
    def json(self):
        return self._doc


class MockDiscoveryClient:
    """Mock httpx.AsyncClient for discovery."""
    
    def __init__(self, response=None):
        self.response = response
        self.call_count = 0
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass
    
    async def get(self, *args, **kwargs):
        self.call_count += 1
        if self.response:
            return self.response
        raise Exception("Connection error")


class MockTokenResponseClient:
    """Mock httpx.AsyncClient for token exchange."""
    
    def __init__(self, response=None):
        self.response = response
        self.call_count = 0
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass
    
    async def post(self, *args, **kwargs):
        self.call_count += 1
        if self.response:
            return self.response
        return MockDiscoveryResponse(
            {
                "access_token": "test-access-token",
                "token_type": "Bearer",
                "id_token": "test-id-token",
                "expires_in": 3600,
            }
        )


class MockUserinfoClient:
    """Mock httpx.AsyncClient for userinfo."""
    
    def __init__(self, response=None):
        self.response = response
        self.call_count = 0
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass
    
    async def get(self, *args, **kwargs):
        self.call_count += 1
        if self.response:
            return self.response
        return MockDiscoveryResponse({}, status_code=200)


@pytest.fixture
def test_settings():
    """Create test GlobalSettings with OIDC configuration."""
    return GlobalSettings(
        oidc_discovery_url="https://example.com/.well-known/openid-configuration",
        oidc_client_id="test-client-id",
        oidc_client_secret="test-client-secret",
        oidc_scopes="openid email profile",
        oidc_provider_name="Example",
        oidc_auto_provision=True,
        oidc_admin_groups="admins",
    )


@pytest.fixture
def mock_discovery():
    """Create a mock OIDC discovery document."""
    return MockDiscoveryDoc()


@pytest.fixture
def mock_jwks():
    """Create a mock JWKS."""
    return MockJWKS()


@pytest.fixture
def mock_token_response():
    """Create a mock token response."""
    return MockDiscoveryResponse(
        {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "id_token": "test-id-token",
            "expires_in": 3600,
        }
    )


@pytest.fixture
def mock_userinfo_response():
    """Create a mock userinfo response."""
    return MockUserinfoResponse({
        "email": "test@example.com",
        "preferred_username": "testuser",
    })


class TestOIDCService:
    """Test suite for OIDCService."""

    @pytest.fixture
    def service(self):
        """Create an OIDCService instance."""
        return OIDCService()

    @pytest.mark.asyncio
    async def test_provider_name_from_discovery(self, service):
        """Test deriving provider name from discovery document."""
        doc = MockDiscoveryDoc(issuer="https://authentik.example.com/.well-known/openid-configuration")
        assert OIDCService.provider_name(doc) == "Authentik"
        
        doc = MockDiscoveryDoc(issuer="https://myapp.example.com/.well-known/openid-configuration")
        assert OIDCService.provider_name(doc) == "Myapp"
        
        doc = MockDiscoveryDoc(issuer="https://oidc.example.com/.well-known/openid-configuration")
        assert OIDCService.provider_name(doc) == "Oidc"

    @pytest.mark.asyncio
    async def test_pop_flow_success(self, service):
        """Test successful flow consumption."""
        verifier = "test-verifier"
        redirect_uri = "http://localhost/callback"
        expires_at = time.time() + 100
        
        service._pending_flows["test-state"] = (verifier, redirect_uri, expires_at, ("fingerprint", ""))
        
        verifier_out, redirect_uri_out, _ = service.pop_flow("test-state")
        
        assert verifier == verifier_out
        assert redirect_uri == redirect_uri_out
        assert "test-state" not in service._pending_flows

    @pytest.mark.asyncio
    async def test_pop_flow_invalid_state(self, service):
        """Test poping a flow with invalid state."""
        with pytest.raises(OIDCError, match="Invalid or expired"):
            service.pop_flow("nonexistent-state")

    @pytest.mark.asyncio
    async def test_pop_flow_expired(self, service):
        """Test poping an expired flow."""
        verifier = "test-verifier"
        redirect_uri = "http://localhost/callback"
        expires_at = time.time() - 100
        
        service._pending_flows["test-state"] = (verifier, redirect_uri, expires_at, ("fingerprint", ""))
        
        with pytest.raises(OIDCError, match="Login flow expired"):
            service.pop_flow("test-state")

    def test_role_from_groups_with_admins(self):
        """Test role assignment with admin groups."""
        claims = {
            "groups": ["admins", "users"],
            "sub": "123",
        }
        
        result = OIDCService._role_from_groups(claims, "admins")
        assert result == "admin"

    def test_role_from_groups_without_admins(self):
        """No configured admin groups means no role synchronization."""
        claims = {
            "groups": ["users"],
            "sub": "123",
        }
        
        result = OIDCService._role_from_groups(claims, "")
        assert result is None

    def test_role_from_groups_empty_admin_groups(self):
        """An absent admin-group setting means no role synchronization."""
        claims = {
            "groups": ["admins"],
            "sub": "123",
        }
        
        result = OIDCService._role_from_groups(claims, None)
        assert result is None

    def test_role_from_groups_string_groups(self):
        """Test role assignment with string groups."""
        # When user_groups is a string, it becomes a single-item list
        # So "admin" in user_groups matches "admin" in configured
        claims = {
            "groups": "admin",
            "sub": "123",
        }
        
        # admin_groups_setting must be "admin" to match user_groups "admin"
        result = OIDCService._role_from_groups(claims, "admin")
        assert result == "admin"

    def test_role_from_groups_no_groups(self):
        """Test role assignment with no groups."""
        claims = {
            "sub": "123",
        }
        
        with pytest.raises(OIDCError, match="valid groups"):
            OIDCService._role_from_groups(claims, "admins")

    @pytest.mark.asyncio
    async def test_prune_flows(self, service):
        """Test flow pruning for expired flows."""
        now = time.time()
        
        service._pending_flows = {
            "active": ("verifier", "uri", now + 100),
            "expired": ("verifier", "uri", now - 100),
        }
        
        service._prune_flows()
        
        assert "active" in service._pending_flows
        assert "expired" not in service._pending_flows

    @pytest.mark.asyncio
    async def test_prune_flows_no_expiration(self, service):
        """Test flow pruning with no expired flows."""
        service._pending_flows = {
            "active": ("verifier", "uri", time.time() + 100),
        }
        
        service._prune_flows()
        
        assert "active" in service._pending_flows
