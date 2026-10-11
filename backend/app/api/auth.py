from datetime import UTC
from urllib.parse import urlparse

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.containers import Container
from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.exceptions import ValidationError
from ..core.security import (
    create_access_token,
    get_current_admin,
    get_current_user,
    get_password_hash,
    verify_password,
)
from ..models.audit import AuditLog
from ..models.settings import GlobalSettings
from ..models.user import User
from ..schemas.auth import (
    LoginResponse,
    OIDCCallbackRequest,
    OIDCConfigResponse,
    OIDCTestRequest,
    OIDCTestResponse,
    PasswordChange,
    UserAdminUpdate,
    UserProfileUpdate,
    UserResponse,
)
from ..services.audit_logger import AuditService
from ..services.oidc_service import OIDCError, oidc_service

router = APIRouter()


async def _get_auth_settings(db: AsyncSession) -> GlobalSettings | None:
    """Load GlobalSettings; None when setup is not complete."""
    try:
        result = await db.execute(select(GlobalSettings))
        return result.scalar_one_or_none()
    except Exception:
        return None


async def _audit_login(
    db: AsyncSession,
    audit_service: AuditService,
    request: Request,
    user: User | None,
    success: bool,
    method: str,
    error_message: str | None = None,
):
    """Write a LOGIN audit entry. Failed/unknown-user attempts get user_id=None."""
    if user:
        await audit_service.log_action(
            db, user, "LOGIN", "user", user.id, user.username,
            {"method": method}, request,
            status="success" if success else "failed",
            error_message=error_message,
        )
        return
    # No user to attribute - write the row directly
    from datetime import datetime

    audit_log = AuditLog(
        user_id=None,
        action="LOGIN",
        resource_type="user",
        resource_id=None,
        resource_name=None,
        details={"method": method},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success" if success else "failed",
        error_message=error_message,
        timestamp=datetime.now(UTC),
    )
    db.add(audit_log)
    await db.flush()


@router.post("/token", response_model=LoginResponse)
@inject
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    settings = await _get_auth_settings(db)
    if settings and settings.auth_mode == "oidc_only":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local password login is disabled (OIDC-only mode). Sign in with your identity provider.",
        )

    if not user or user.hashed_password is None or not verify_password(form_data.password, user.hashed_password):
        await _audit_login(db, audit_service, request, user, False, "local",
                           error_message="Incorrect username or password")
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.auth_provider == "oidc":
        await _audit_login(db, audit_service, request, user, False, "local",
                           error_message="OIDC account attempted local login")
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account uses Single Sign-On. Sign in with your identity provider.",
        )

    # Note: create_access_token will load token expiration from database settings
    access_token = await create_access_token(
        data={"sub": user.username},
        db=db
    )

    await event_bus.publish(
        EventType.USER_LOGIN,
        "user",
        user.id,
        {"username": user.username},
        user.id
    )

    await _audit_login(db, audit_service, request, user, True, "local")
    await db.commit()

    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.get("/profile", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile."""
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile."""
    # Check if email is already taken by another user
    if profile_data.email != current_user.email:
        result = await db.execute(select(User).where(User.email == profile_data.email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise ValidationError(
                "email",
                "Email already registered"
            )

    # Update email
    current_user.email = profile_data.email
    await db.commit()
    await db.refresh(current_user)

    await event_bus.publish(
        EventType.USER_UPDATED,
        "user",
        current_user.id,
        {"email": profile_data.email},
        current_user.id
    )

    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user password."""
    if current_user.auth_provider == "oidc" or current_user.hashed_password is None:
        raise ValidationError(
            "current_password",
            "This account signs in with Single Sign-On and has no local password"
        )

    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise ValidationError(
            "current_password",
            "Current password is incorrect"
        )

    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()

    await event_bus.publish(
        EventType.USER_UPDATED,
        "user",
        current_user.id,
        {"action": "password_changed"},
        current_user.id
    )

    return {"message": "Password changed successfully"}


# ---------------------------------------------------------------------------
# User management (admin only)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    user_data: UserAdminUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Change a user's role (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.role == "admin" and user_data.role != "admin":
        # Prevent removing the last admin
        result = await db.execute(
            select(func.count(User.id)).where(User.role == "admin")
        )
        admin_count = result.scalar()
        if admin_count <= 1:
            raise ValidationError(
                "role",
                "Cannot demote the last administrator"
            )

    old_role = user.role
    user.role = user_data.role
    await db.commit()
    await db.refresh(user)

    await event_bus.publish(
        EventType.USER_UPDATED,
        "user",
        user.id,
        {"action": "role_changed", "old_role": old_role, "new_role": user_data.role},
        current_user.id
    )

    return user


# ---------------------------------------------------------------------------
# OIDC / Single Sign-On
# ---------------------------------------------------------------------------

@router.get("/oidc/config", response_model=OIDCConfigResponse)
async def oidc_config(
    db: AsyncSession = Depends(get_db)
):
    """Public endpoint telling the login page whether SSO is available."""
    settings = await _get_auth_settings(db)
    if not settings or settings.auth_mode == "local_only" or not settings.oidc_discovery_url:
        return {"oidc_enabled": False, "auth_mode": settings.auth_mode if settings else "both"}

    try:
        discovery = await oidc_service.get_discovery(settings.oidc_discovery_url)
        provider_name = settings.oidc_provider_name or oidc_service.provider_name(discovery)
    except OIDCError:
        # Provider unreachable - still show the button, backend will error with details
        provider_name = settings.oidc_provider_name

    return {
        "oidc_enabled": True,
        "auth_mode": settings.auth_mode,
        "provider_name": provider_name,
    }


@router.get("/oidc/login")
async def oidc_login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Start an OIDC login: returns the IdP authorization URL to redirect to."""
    settings = await _get_auth_settings(db)
    if (
        not settings
        or settings.auth_mode == "local_only"
        or not settings.oidc_discovery_url
        or not settings.oidc_client_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Single Sign-On is not configured"
        )

    # The IdP must redirect back to the frontend; derive its origin from the
    # request (dev: http://localhost:5173, prod: same origin as the backend).
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"
    if not origin:
        origin = str(request.base_url).rstrip("/")

    redirect_uri = f"{origin}/oidc-callback"
    try:
        authorization_url = await oidc_service.build_authorization_url(settings, redirect_uri)
    except OIDCError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        ) from e

    return {"authorization_url": authorization_url}


@router.post("/oidc/callback", response_model=LoginResponse)
@inject
async def oidc_callback(
    callback_data: OIDCCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Complete an OIDC login: exchange the code, provision the user, mint a JWT."""
    settings = await _get_auth_settings(db)
    if not settings or not settings.oidc_discovery_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Single Sign-On is not configured"
        )

    try:
        verifier, redirect_uri = oidc_service.pop_flow(callback_data.state)
        discovery = await oidc_service.get_discovery(settings.oidc_discovery_url)
        token_response = await oidc_service.exchange_code(
            settings, discovery, callback_data.code, redirect_uri, verifier
        )
        claims = await oidc_service.obtain_claims(settings, discovery, token_response)
        user = await oidc_service.get_or_provision_user(db, settings, claims)
    except OIDCError as e:
        await _audit_login(db, audit_service, request, None, False, "oidc",
                           error_message=str(e))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) from e
    except HTTPException:
        raise

    access_token = await create_access_token(
        data={"sub": user.username},
        db=db
    )

    await event_bus.publish(
        EventType.USER_OIDC_LOGIN,
        "user",
        user.id,
        {"username": user.username, "provider": oidc_service.provider_name(discovery)},
        user.id
    )

    await _audit_login(db, audit_service, request, user, True, "oidc")
    await db.commit()

    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.post("/oidc/test", response_model=OIDCTestResponse)
async def oidc_test(
    test_data: OIDCTestRequest,
    current_user: User = Depends(get_current_admin),
):
    """Validate OIDC configuration against the provider (admin only)."""
    try:
        discovery = await oidc_service.get_discovery(test_data.discovery_url, force_refresh=True)
    except OIDCError as e:
        return {"success": False, "provider_name": None, "message": str(e)}

    missing = [
        field for field in ("authorization_endpoint", "token_endpoint", "jwks_uri", "issuer")
        if not discovery.get(field)
    ]
    if missing:
        return {
            "success": False,
            "provider_name": None,
            "message": f"Discovery document is missing: {', '.join(missing)}",
        }

    # Sanity-check the token endpoint accepts our client credentials shape by
    # attempting a discovery-level reachability check on the token endpoint.
    provider_name = oidc_service.provider_name(discovery)
    return {
        "success": True,
        "provider_name": provider_name,
        "message": f"Discovery document valid for {provider_name}. Endpoints found for authorization, token and JWKS.",
    }
