from datetime import datetime, timedelta
import hashlib
import hmac
import json
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..models.settings import GlobalSettings
from .database import get_db

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer with auto_error=False to make it optional
security = HTTPBearer(auto_error=False)

OIDC_SECURITY_FIELDS = (
    "oidc_discovery_url", "oidc_client_id", "oidc_client_secret",
    "oidc_scopes", "oidc_admin_groups",
)


def oidc_configuration_fingerprint(settings: GlobalSettings) -> str:
    values = [getattr(settings, field) for field in OIDC_SECURITY_FIELDS]
    return hmac.new(settings.secret_key.encode(), json.dumps(values).encode(), hashlib.sha256).hexdigest()


def auth_generations(settings: GlobalSettings) -> tuple[str, str]:
    # After setup, the otherwise unused progress column stores two hex counters.
    state = settings.setup_current_step
    if settings.setup_completed and state and state.startswith("r"):
        if len(state) != 17 or any(char not in "0123456789abcdef" for char in state[1:]):
            raise JWTError("Invalid authentication revocation state")
        return tuple("" if value == "00000000" else value for value in (state[1:9], state[9:17]))
    return "", ""


async def lock_auth_settings(db: AsyncSession) -> GlobalSettings | None:
    await db.execute(update(GlobalSettings).values(updated_at=GlobalSettings.updated_at))
    return (await db.execute(select(GlobalSettings).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()


async def authenticate_locked(db: AsyncSession, settings: GlobalSettings, token: str | None) -> User:
    require_secure_signing_key(settings)
    error = HTTPException(status_code=401, detail="Could not validate credentials")
    if settings.setup_completed and settings.disable_auth:
        user = (await db.execute(select(User).order_by(User.id).limit(1).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    else:
        try:
            if not token:
                raise JWTError("Missing token")
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm], options={"require_exp": True})
            username = payload.get("sub")
            if not isinstance(username, str) or not username:
                raise JWTError("Missing subject")
        except JWTError:
            raise error from None
        user = (await db.execute(select(User).where(User.username == username).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        if user:
            try:
                validate_auth_method(payload, settings, user)
            except JWTError:
                raise error from None
    if user is None:
        raise error
    return user


def require_secure_signing_key(settings: GlobalSettings | None) -> None:
    if settings and settings.secret_key == "temporary-key-will-be-replaced":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Insecure legacy signing key. Local operator recovery required.",
        )


async def get_settings_for_auth(db: AsyncSession) -> GlobalSettings | None:
    """
    Get settings for authentication.
    Returns None if setup is not complete (allows setup endpoints to work).
    """
    try:
        result = await db.execute(select(GlobalSettings))
        settings = result.scalar_one_or_none()
        return settings
    except Exception:
        # During initial setup, table might not exist yet
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    # Truncate password to 72 bytes for bcrypt
    return pwd_context.verify(plain_password[:72], hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Truncate password to 72 bytes for bcrypt
    return pwd_context.hash(password[:72])


def validate_auth_method(payload: dict, settings: GlobalSettings, user: User) -> None:
    """Apply the current mode to both new and pre-auth_method access tokens."""
    if settings.auth_mode not in ("both", "local_only", "oidc_only"):
        raise JWTError("Invalid authentication mode")
    method = payload.get("auth_method")
    if method is None and "auth_method" not in payload:
        # Older OIDC tokens carried this signed fingerprint; other legacy tokens
        # cannot safely be assumed to have authenticated with OIDC.
        method = "oidc" if isinstance(payload.get("oidc_config"), str) and payload["oidc_config"] else "local"
    if method not in ("local", "oidc"):
        raise JWTError("Invalid authentication method")
    local_generation, oidc_generation = auth_generations(settings)
    if "auth_method" not in payload and method == "local" and (oidc_generation or settings.auth_mode == "local_only"):
        raise JWTError("Ambiguous legacy session revoked")
    expected_generation = oidc_generation if method == "oidc" else local_generation
    if payload.get("auth_generation", "") != expected_generation:
        raise JWTError("Authentication session revoked")
    if method == "oidc":
        fingerprint = payload.get("oidc_config")
        if not isinstance(fingerprint, str) or not hmac.compare_digest(
            fingerprint.encode("utf-8"), oidc_configuration_fingerprint(settings).encode("ascii")
        ):
            raise JWTError("OIDC configuration changed")
    if settings.auth_mode == "local_only" and method == "oidc":
        raise JWTError("OIDC authentication disabled")
    if settings.auth_mode == "oidc_only" and method != "oidc":
        if settings.setup_completed or user.role != "admin" or user.auth_provider != "local":
            raise JWTError("Local authentication disabled")


async def create_access_token(data: dict, db: AsyncSession, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    settings = await get_settings_for_auth(db)
    require_secure_signing_key(settings)
    
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application not configured. Please complete setup first."
        )
    
    to_encode = data.copy()
    if to_encode.get("auth_method") in ("local", "oidc"):
        local_generation, oidc_generation = auth_generations(settings)
        to_encode["auth_generation"] = oidc_generation if to_encode["auth_method"] == "oidc" else local_generation
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get the current authenticated user."""
    
    # Get settings
    settings = await get_settings_for_auth(db)
    require_secure_signing_key(settings)
    
    # If settings don't exist yet, we're in setup mode - allow access to setup endpoints only
    # This is handled by route-level checks in setup.py
    
    if settings and settings.setup_completed and settings.disable_auth:
        # Authentication bypass is available only after setup has completed.
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            return user
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception
    
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application not configured. Please complete setup first."
        )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm], options={"require_exp": True})
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    try:
        validate_auth_method(payload, settings, user)
    except JWTError:
        raise credentials_exception from None

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that only allows users with the admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user
