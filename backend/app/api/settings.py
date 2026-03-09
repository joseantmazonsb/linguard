import ipaddress
import subprocess

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings as app_settings
from ..core.config_loader import config_loader
from ..core.containers import Container
from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.security import get_current_user
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
        settings = GlobalSettings(
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
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()

    if not settings:
        # Create if doesn't exist
        settings = GlobalSettings(
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

    # Store old values for audit
    old_values = {
        "dns_primary": settings.dns_primary,
        "dns_secondary": settings.dns_secondary
    }

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

