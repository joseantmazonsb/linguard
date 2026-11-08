import ipaddress
from secrets import token_urlsafe
import subprocess

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings as app_settings
from ..core.config_loader import config_loader
from ..core.containers import Container
from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.security import (
    OIDC_SECURITY_FIELDS, auth_generations, get_current_user, oidc_configuration_fingerprint,
    validate_auth_method, authenticate_locked, lock_auth_settings,
)
from ..models.settings import GlobalSettings
from ..models.user import User
from ..schemas.settings import GlobalSettingsResponse, GlobalSettingsUpdate
from ..services.audit_logger import AuditService

router = APIRouter()

@router.get("/global", response_model=GlobalSettingsResponse)
async def get_global_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()

    if not settings:
        # Bootstrap a row. secret_key and backup_dir have no schema default but
        # are NOT NULL, so they must be filled to keep the insert valid; the
        # setup wizard replaces the placeholder key when it runs.
        settings = GlobalSettings(
            secret_key=token_urlsafe(32),
            backup_dir="./backups",
            metrics_collection_interval_minutes=5,
            metrics_retention_days=90,
            metrics_global_notifications_per_hour=50,
        )
        db.add(settings)
        await db.flush()
        await db.refresh(settings)

    # Auto-detect database type from DATABASE_URL if not set
    if not settings.database_type or not settings.database_url:
        db_url = config_loader.get_database_url()
        settings.database_url = db_url
        
        # Detect database type from URL
        if "sqlite" in db_url.lower():
            settings.database_type = "sqlite"
        elif "postgresql" in db_url.lower():
            settings.database_type = "postgresql"
        elif "mysql" in db_url.lower():
            settings.database_type = "mysql"
        else:
            settings.database_type = "unknown"
        
        await db.commit()
        await db.refresh(settings)

    return settings


@router.put("/global", response_model=GlobalSettingsResponse)
@inject
async def update_global_settings(
    settings_data: GlobalSettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Update global settings (DNS servers and IP pools)"""
    # Get existing settings
    # Serialize settings writes, including on SQLite where FOR UPDATE is ignored.
    settings = await lock_auth_settings(db)

    if settings:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        current_user = await authenticate_locked(db, settings, token if scheme.lower() == "bearer" else None)
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Administrator privileges required")

    if not settings:
        # Create if doesn't exist (same NOT NULL bootstrap as the GET handler)
        settings = GlobalSettings(
            secret_key=token_urlsafe(32),
            backup_dir="./backups",
            metrics_collection_interval_minutes=5,
            metrics_retention_days=90,
            metrics_global_notifications_per_hour=50,
        )
        db.add(settings)
        await db.flush()

    # Validate DNS addresses if provided
    update_data = settings_data.model_dump(exclude_unset=True)

    if "dns_primary" in update_data and update_data["dns_primary"]:
        try:
            ipaddress.ip_address(update_data["dns_primary"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid primary DNS address: {update_data['dns_primary']}"
            ) from None

    if "dns_secondary" in update_data and update_data["dns_secondary"]:
        try:
            ipaddress.ip_address(update_data["dns_secondary"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid secondary DNS address: {update_data['dns_secondary']}"
            ) from None

    # Validate log_path if provided
    if "log_path" in update_data:
        log_path_value = update_data["log_path"]
        if log_path_value is None or (isinstance(log_path_value, str) and not log_path_value.strip()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Log file path cannot be empty. Please provide a valid file path."
            )

    # Validate backup schedule settings
    # Only validate time fields if periodic backups are enabled
    backup_periodic_enabled = update_data.get("backup_periodic_enabled", settings.backup_periodic_enabled)
    
    if "backup_schedule_frequency" in update_data:
        frequency = update_data["backup_schedule_frequency"]
        if frequency not in ["daily", "weekly", "monthly"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backup schedule frequency must be 'daily', 'weekly', or 'monthly'."
            )

    if "backup_schedule_hour" in update_data:
        hour = update_data["backup_schedule_hour"]
        if hour is not None:  # Allow None when periodic backups are disabled
            if not isinstance(hour, int) or hour < 0 or hour > 23:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Backup schedule hour must be between 0 and 23."
                )

    if "backup_schedule_minute" in update_data:
        minute = update_data["backup_schedule_minute"]
        if minute is not None:  # Allow None when periodic backups are disabled
            if not isinstance(minute, int) or minute < 0 or minute > 59:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Backup schedule minute must be between 0 and 59."
                )

    # Validate auth_mode if provided
    if "auth_mode" in update_data and update_data["auth_mode"] not in ("both", "local_only", "oidc_only"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication mode must be 'both', 'local_only', or 'oidc_only'."
        )

    # Validate OIDC discovery URL if provided
    if "oidc_discovery_url" in update_data and update_data["oidc_discovery_url"]:
        url = update_data["oidc_discovery_url"]
        if not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OIDC discovery URL must start with http:// or https://."
            )

    if any(field in update_data and update_data[field] != getattr(settings, field)
           for field in ("oidc_discovery_url", "oidc_client_id")):
        linked_user = (await db.execute(
            select(User.id).where(User.oidc_sub.is_not(None)).limit(1).with_for_update()
        )).scalar_one_or_none()
        if linked_user is not None:
            raise HTTPException(status_code=400, detail="OIDC provider or client cannot be changed while accounts are linked.")

    resulting_mode = update_data.get("auth_mode", settings.auth_mode)
    if resulting_mode == "oidc_only":
        if not settings.setup_completed:
            raise HTTPException(status_code=400, detail="Complete setup before enabling OIDC-only mode.")
        if any(field in update_data and update_data[field] != getattr(settings, field) for field in OIDC_SECURITY_FIELDS):
            raise HTTPException(status_code=400, detail="Switch to both authentication modes before changing OIDC configuration.")
        if settings.auth_mode != "oidc_only":
            if any(field in update_data and update_data[field] != getattr(settings, field) for field in ("secret_key", "algorithm")):
                raise HTTPException(status_code=400, detail="Change signing settings and sign in again before enabling OIDC-only mode.")
            authorization = request.headers.get("authorization", "")
            scheme, _, token = authorization.partition(" ")
            try:
                if scheme.lower() != "bearer" or not token or not settings.oidc_discovery_url or not settings.oidc_client_id:
                    raise JWTError("OIDC session required")
                claims = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm], options={"require_exp": True})
                validate_auth_method(claims, settings, current_user)
                if (claims.get("sub") != current_user.username or not current_user.oidc_sub
                        or claims.get("auth_method", "oidc") != "oidc"
                        or claims.get("oidc_config") != oidc_configuration_fingerprint(settings)):
                    raise JWTError("OIDC session required")
            except JWTError:
                raise HTTPException(status_code=400, detail="Sign in as an OIDC administrator before enabling OIDC-only mode.") from None

    # The backup schedule columns are NOT NULL and the response schema declares
    # them as integers, so a null time (sent when periodic backups are being
    # disabled) means "keep the stored schedule" rather than "store NULL".
    for time_field in ("backup_schedule_hour", "backup_schedule_minute"):
        if time_field in update_data and update_data[time_field] is None:
            update_data.pop(time_field)

    # Store old values for audit
    old_values = {
        "dns_primary": settings.dns_primary,
        "dns_secondary": settings.dns_secondary
    }

    if settings.setup_completed:
        local_generation, oidc_generation = auth_generations(settings)
        changed = False
        if settings.auth_mode != "oidc_only" and resulting_mode == "oidc_only":
            if local_generation == "ffffffff":
                raise HTTPException(status_code=503, detail="Authentication revocation counter exhausted.")
            local_generation = f"{int(local_generation or '0', 16) + 1:08x}"
            changed = True
        if ((settings.auth_mode != resulting_mode and "local_only" in (settings.auth_mode, resulting_mode)) or
                any(field in update_data and update_data[field] != getattr(settings, field) for field in OIDC_SECURITY_FIELDS)):
            if oidc_generation == "ffffffff":
                raise HTTPException(status_code=503, detail="Authentication revocation counter exhausted.")
            oidc_generation = f"{int(oidc_generation or '0', 16) + 1:08x}"
            changed = True
        if changed:
            settings.setup_current_step = f"r{local_generation or '00000000'}{oidc_generation or '00000000'}"

    # Update fields
    for field, value in update_data.items():
        setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)

    # Reconfigure logging if log_path was changed
    if "log_path" in update_data:
        from ..main import configure_logging
        configure_logging(settings.log_path)

    # Log audit event
    await audit_service.log_action(
        db, current_user, "UPDATE", "settings", settings.id, "Global Settings",
        {"old": old_values, "new": update_data}, request
    )

    # Publish event
    await event_bus.publish(
        EventType.SETTINGS_UPDATED,
        "settings",
        settings.id,
        {"changes": list(update_data.keys())},
        current_user.id
    )

    return settings
