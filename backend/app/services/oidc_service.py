"""
OIDC (OpenID Connect) service.

Implements the Authorization Code flow with PKCE, backed by any compliant
identity provider (Authentik, Keycloak, etc.) via its discovery document.

The backend mediates the whole flow: the browser is redirected to the IdP,
the frontend callback route hands the authorization code back to the backend,
and the backend exchanges/validates it and mints a local Linguard JWT so the
rest of the app (REST auth, WebSocket auth, token expiry) works unchanged.
"""

import base64
import hashlib
import logging
import secrets
import time
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import authenticate_locked, auth_generations, lock_auth_settings, oidc_configuration_fingerprint, verify_password
from ..models.user import User

logger = logging.getLogger(__name__)

# How long a login flow (state + PKCE verifier) may sit between authorize and callback
FLOW_TTL_SECONDS = 300
# How long a discovery document is cached before refetching
DISCOVERY_TTL_SECONDS = 3600


class OIDCError(Exception):
    """Raised for any OIDC flow failure with a user-presentable message."""


class OIDCService:
    """Handles discovery, authorization URLs, code exchange and user provisioning."""

    def __init__(self):
        # state -> (code_verifier, redirect_uri, expires_at, configuration binding)
        self._pending_flows: dict[str, tuple[str, str, float, tuple[str, str]]] = {}
        # discovery_url -> (document, fetched_at)
        self._discovery_cache: dict[str, tuple[dict, float]] = {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def get_discovery(self, discovery_url: str, force_refresh: bool = False) -> dict:
        """Fetch (and cache) the provider's OpenID Connect discovery document."""
        cached = self._discovery_cache.get(discovery_url)
        if cached and not force_refresh and time.time() - cached[1] < DISCOVERY_TTL_SECONDS:
            return cached[0]

        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                response = await client.get(discovery_url)
                response.raise_for_status()
                doc = response.json()
        except httpx.HTTPError as e:
            raise OIDCError(f"Could not reach discovery URL: {e}") from e
        except ValueError as e:
            raise OIDCError("Discovery URL did not return valid JSON") from e

        for field in ("authorization_endpoint", "token_endpoint", "issuer"):
            if not doc.get(field):
                raise OIDCError(f"Discovery document is missing required field '{field}'")

        self._discovery_cache[discovery_url] = (doc, time.time())
        return doc

    @staticmethod
    def provider_name(discovery: dict) -> str:
        """Derive a human-friendly provider name from the issuer URL."""
        issuer = discovery.get("issuer", "")
        hostname = urlparse(issuer).hostname or "OIDC"
        # Strip common prefixes/suffixes: "authentik.example.com" -> "authentik"
        parts = hostname.split(".")
        name = parts[0] if parts else "OIDC"
        return name.capitalize()

    # ------------------------------------------------------------------
    # Authorization Code + PKCE flow
    # ------------------------------------------------------------------

    @staticmethod
    def _pkce_pair() -> tuple[str, str]:
        """Generate a (code_verifier, code_challenge) pair using S256."""
        verifier = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    async def build_authorization_url(
        self,
        settings,
        redirect_uri: str,
        force_refresh: bool = False,
    ) -> str:
        """Build the IdP authorization URL and register a pending login flow."""
        binding = (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])
        discovery = await self.get_discovery(settings.oidc_discovery_url, force_refresh=force_refresh)

        verifier, challenge = self._pkce_pair()
        state = secrets.token_urlsafe(32)
        self._pending_flows[state] = (verifier, redirect_uri, time.time() + FLOW_TTL_SECONDS, binding)
        self._prune_flows()

        params = {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": redirect_uri,
            "scope": settings.oidc_scopes or "openid email profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        separator = "&" if "?" in discovery["authorization_endpoint"] else "?"
        return f"{discovery['authorization_endpoint']}{separator}{urlencode(params)}"

    def _prune_flows(self):
        now = time.time()
        expired = [s for s, flow in self._pending_flows.items() if flow[2] < now]
        for state in expired:
            del self._pending_flows[state]

    def pop_flow(self, state: str) -> tuple[str, str, tuple[str, str]]:
        """
        Consume a pending login flow.

        Returns (code_verifier, redirect_uri, configuration binding). Raises OIDCError for unknown,
        expired or already-used states.
        """
        flow = self._pending_flows.pop(state, None)
        if not flow:
            raise OIDCError("Invalid or expired login state. Please try signing in again.")
        verifier, redirect_uri, expires_at, binding = flow
        if expires_at < time.time():
            raise OIDCError("Login flow expired. Please try signing in again.")
        return verifier, redirect_uri, binding

    @staticmethod
    async def lock_flow_settings(db: AsyncSession, binding: tuple[str, str], link: bool = False):
        settings = await lock_auth_settings(db)
        if (not settings or settings.auth_mode not in (("both",) if link else ("both", "oidc_only"))
                or binding != (oidc_configuration_fingerprint(settings), auth_generations(settings)[1])):
            raise OIDCError("OIDC configuration changed. Please sign in again.")
        return settings

    # ------------------------------------------------------------------
    # Code exchange + ID token validation
    # ------------------------------------------------------------------

    async def exchange_code(
        self,
        settings,
        discovery: dict,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> dict:
        """Exchange the authorization code for tokens at the IdP token endpoint."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
            "code_verifier": code_verifier,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(discovery["token_endpoint"], data=data)
                if response.status_code != 200:
                    detail = response.text[:300]
                    logger.warning(f"OIDC token exchange failed: {response.status_code} {detail}")
                    raise OIDCError("The identity provider rejected the login attempt.")
                return response.json()
        except httpx.HTTPError as e:
            raise OIDCError(f"Could not reach the identity provider's token endpoint: {e}") from e

    async def fetch_userinfo(self, discovery: dict, access_token: str) -> dict | None:
        """Fetch additional claims from the userinfo endpoint, if advertised."""
        userinfo_endpoint = discovery.get("userinfo_endpoint")
        if not userinfo_endpoint:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    userinfo_endpoint, headers={"Authorization": f"Bearer {access_token}"}
                )
                if response.status_code != 200:
                    logger.warning(f"OIDC userinfo returned {response.status_code}; using ID token claims only")
                    return None
                return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"OIDC userinfo request failed: {e}")
            return None

    async def get_jwks(self, discovery: dict) -> dict:
        """Fetch the provider's JWKS (cached alongside the discovery document)."""
        jwks_uri = discovery.get("jwks_uri")
        if not jwks_uri:
            raise OIDCError("Discovery document does not advertise a jwks_uri")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(jwks_uri)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise OIDCError(f"Could not fetch the identity provider's signing keys: {e}") from e

    async def validate_id_token(self, settings, discovery: dict, id_token: str) -> dict:
        """Validate the ID token signature, issuer and audience; return its claims."""
        jwks = await self.get_jwks(discovery)
        try:
            header = jwt.get_unverified_header(id_token)
        except JWTError as e:
            raise OIDCError("Identity provider returned an malformed ID token") from e

        kid = header.get("kid")
        key = None
        for jwk_dict in jwks.get("keys", []):
            if jwk_dict.get("kid") == kid:
                key = jwk_dict
                break
        if key is None:
            raise OIDCError("ID token signing key not found in the provider's JWKS")

        algorithms = [header.get("alg", "RS256")]
        try:
            claims = jwt.decode(
                id_token,
                key,
                algorithms=algorithms,
                audience=settings.oidc_client_id,
                issuer=discovery["issuer"],
                options={"leeway": 60, "require_exp": True},
            )
        except JWTError as e:
            raise OIDCError(f"ID token validation failed: {e}") from e
        return claims

    async def obtain_claims(self, settings, discovery: dict, token_response: dict) -> dict:
        """Combine ID token claims with userinfo claims (userinfo wins on conflict)."""
        id_token = token_response.get("id_token")
        if not id_token:
            raise OIDCError("Identity provider did not return an ID token")
        claims = await self.validate_id_token(settings, discovery, id_token)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise OIDCError("ID token is missing a valid subject")

        userinfo = await self.fetch_userinfo(discovery, token_response.get("access_token", ""))
        if userinfo is not None:
            if not isinstance(userinfo, dict) or userinfo.get("sub") != subject:
                raise OIDCError("UserInfo subject does not match the ID token subject")
            if "email" in userinfo and "email_verified" not in userinfo:
                claims.pop("email_verified", None)
            if "email_verified" in userinfo and "email" not in userinfo:
                userinfo = {key: value for key, value in userinfo.items() if key != "email_verified"}
            claims.update(userinfo)
        return claims

    # ------------------------------------------------------------------
    # User provisioning
    # ------------------------------------------------------------------

    @staticmethod
    def _role_from_groups(claims: dict, admin_groups_setting: str) -> str | None:
        """Map groups to a role, or return None when role sync is not configured."""
        configured = {g.strip() for g in (admin_groups_setting or "").split(",") if g.strip()}
        if not configured:
            return None
        user_groups = claims.get("groups")
        if isinstance(user_groups, str):
            user_groups = [user_groups]
        if not isinstance(user_groups, list) or not all(isinstance(group, str) for group in user_groups):
            raise OIDCError("Identity provider did not return valid groups")
        if configured.intersection(user_groups):
            return "admin"
        return "standard"

    async def link_local_account(
        self, db: AsyncSession, settings, username: str, password: str, state: str, code: str, token: str
    ) -> User:
        """Link only after proving control of both the local and OIDC accounts."""
        verifier, redirect_uri, binding = self.pop_flow(state)
        if binding != (oidc_configuration_fingerprint(settings), auth_generations(settings)[1]):
            raise OIDCError("OIDC configuration changed. Please sign in again.")
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if (not user or user.auth_provider != "local" or user.oidc_sub or not user.hashed_password
                or not verify_password(password, user.hashed_password)):
            raise OIDCError("Unable to link local account")

        discovery = await self.get_discovery(settings.oidc_discovery_url)
        tokens = await self.exchange_code(settings, discovery, code, redirect_uri, verifier)
        claims = await self.obtain_claims(settings, discovery, tokens)
        settings = await self.lock_flow_settings(db, binding, link=True)
        try:
            authenticated = await authenticate_locked(db, settings, token)
        except HTTPException as exc:
            raise OIDCError("Authentication required") from exc
        if authenticated.username != username:
            raise OIDCError("Authentication required")
        result = await db.execute(select(User).where(User.username == username).with_for_update().execution_options(populate_existing=True))
        user = result.scalar_one_or_none()
        if (not user or user.auth_provider != "local" or user.oidc_sub or not user.hashed_password
                or not verify_password(password, user.hashed_password)):
            raise OIDCError("Unable to link local account")
        subject = claims.get("sub")
        if (not isinstance(subject, str) or not subject or claims.get("email_verified") is not True
                or claims.get("email") != user.email):
            raise OIDCError("Unable to link local account")
        if user.role == "admin" and self._role_from_groups(claims, settings.oidc_admin_groups) != "admin":
            raise OIDCError("OIDC identity is not in an administrator group")
        result = await db.execute(select(User).where(User.oidc_sub == subject))
        if result.scalar_one_or_none():
            raise OIDCError("OIDC identity is already linked")
        user.oidc_sub = subject
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def _unique_username(db: AsyncSession, base: str) -> str:
        """Return a username derived from `base` that is not already taken."""
        candidate = base or "user"
        result = await db.execute(select(User).where(User.username == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
        counter = 2
        while True:
            candidate = f"{base}-{counter}"
            result = await db.execute(select(User).where(User.username == candidate))
            if result.scalar_one_or_none() is None:
                return candidate
            counter += 1

    async def get_or_provision_user(self, db: AsyncSession, settings, claims: dict) -> User:
        """
        Find or create the Linguard user for the given OIDC claims.

        Match by oidc_sub or (optionally) auto-provision a new user. The caller
        owns the transaction and holds the settings lock until commit.
        Email collisions are never linked without an authenticated linking flow.
        """
        oidc_sub = claims.get("sub")
        if not oidc_sub:
            raise OIDCError("Identity provider did not return a 'sub' claim")

        # 1. Existing OIDC-linked user
        result = await db.execute(select(User).where(User.oidc_sub == oidc_sub))
        user = result.scalar_one_or_none()
        if user:
            if user.auth_provider == "oidc":
                role = self._role_from_groups(claims, settings.oidc_admin_groups)
                if role is not None and user.role != role:
                    if user.role == "admin" and role != "admin":
                        # Serialize demotions, including on SQLite where FOR UPDATE is ignored.
                        await db.execute(update(User).where(User.role == "admin").values(
                            role=User.role, updated_at=User.updated_at
                        ))
                        admins = (await db.execute(
                            select(User).where(User.role == "admin").order_by(User.id).with_for_update()
                        )).scalars().all()
                        oidc_only = getattr(settings, "auth_mode", None) == "oidc_only"
                        if not any(
                            admin.id != user.id and (not oidc_only or admin.oidc_sub)
                            for admin in admins
                        ):
                            raise OIDCError("Cannot demote the last administrator; OIDC login denied")
                    user.role = role
                    await db.flush()
            elif user.role == "admin":
                role = self._role_from_groups(claims, settings.oidc_admin_groups)
                if role is not None and role != "admin":
                    raise OIDCError("OIDC identity is not in an administrator group")
            return user

        email = claims.get("email")

        # 2. Never link an account solely on the basis of an email claim.
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                raise OIDCError("An account with this email already exists; automatic linking is not allowed")

        # 3. Auto-provision
        if not settings.oidc_auto_provision:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not registered in Linguard and automatic provisioning is disabled.",
            )

        if not email:
            raise OIDCError("Identity provider did not return an email address; cannot provision user")

        base_username = claims.get("preferred_username") or email.split("@")[0]
        username = await self._unique_username(db, str(base_username)[:50])
        role = self._role_from_groups(claims, settings.oidc_admin_groups) or "standard"

        user = User(
            username=username,
            email=email,
            hashed_password=None,
            role=role,
            auth_provider="oidc",
            oidc_sub=oidc_sub,
        )
        db.add(user)
        await db.flush()
        logger.info(f"Provisioned OIDC user '{username}' (role={role})")
        return user


# Singleton instance used by the auth API
oidc_service = OIDCService()
