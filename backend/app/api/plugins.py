from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.containers import Container
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.plugin import Plugin
from ..models.settings import GlobalSettings
from ..models.user import User
from ..plugins.manager import PluginManager
from ..schemas.plugin import (
    PluginConfigUpdate,
    PluginDeleteResponse,
    PluginDisableResponse,
    PluginDiscoverResponse,
    PluginEnableResponse,
    PluginListResponse,
    PluginResponse,
)
from ..services.audit_logger import AuditService

router = APIRouter()


@router.get("/", response_model=PluginListResponse)
@inject
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all discovered plugins."""
    result = await db.execute(select(Plugin))
    plugins = result.scalars().all()
    
    return PluginListResponse(
        plugins=plugins,
        total=len(plugins)
    )


@router.get("/{plugin_id}", response_model=PluginResponse)
@inject
async def get_plugin(
    plugin_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get plugin details including config schema."""
    result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin with id {plugin_id} not found"
        )
    
    return plugin


@router.post("/discover", response_model=PluginDiscoverResponse)
@inject
async def discover_plugins(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    plugin_manager: PluginManager = Depends(Provide[Container.plugin_manager]),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Manually trigger plugin discovery."""
    # Get plugins directory from global settings
    result = await db.execute(select(GlobalSettings))
    global_settings = result.scalar_one_or_none()
    plugins_dir = global_settings.plugins_directory if global_settings else "./plugins"
    if not plugins_dir:
        plugins_dir = "./plugins"
    
    newly_discovered = await plugin_manager.discover_plugins(plugins_dir, db)
    await db.commit()
    
    # Get total plugin count
    result = await db.execute(select(Plugin))
    total_plugins = len(result.scalars().all())
    
    # Log audit
    await audit_service.log_action(
        db, current_user, "DISCOVER", "plugin", None, f"{newly_discovered} plugins",
        {"newly_discovered": newly_discovered, "total": total_plugins}, request
    )
    
    return PluginDiscoverResponse(
        newly_discovered=newly_discovered,
        total_plugins=total_plugins,
        message=f"Discovered {newly_discovered} new plugin(s). Total: {total_plugins}"
    )


@router.post("/{plugin_id}/enable", response_model=PluginEnableResponse)
@inject
async def enable_plugin(
    plugin_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    plugin_manager: PluginManager = Depends(Provide[Container.plugin_manager]),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Enable a plugin."""
    result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin with id {plugin_id} not found"
        )
    
    if plugin.enabled:
        return PluginEnableResponse(
            success=True,
            message=f"Plugin '{plugin.name}' is already enabled",
            plugin=plugin
        )
    
    try:
        await plugin_manager.enable_plugin(plugin_id, db)
        await db.commit()
        
        # Refresh plugin data
        await db.refresh(plugin)
        
        # Log audit
        await audit_service.log_action(
            db, current_user, "ENABLE", "plugin", plugin_id, plugin.name,
            {"version": plugin.version}, request
        )
        
        return PluginEnableResponse(
            success=True,
            message=f"Plugin '{plugin.name}' enabled successfully",
            plugin=plugin
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable plugin: {str(e)}"
        )


@router.post("/{plugin_id}/disable", response_model=PluginDisableResponse)
@inject
async def disable_plugin(
    plugin_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    plugin_manager: PluginManager = Depends(Provide[Container.plugin_manager]),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Disable a plugin and all integrations that use it."""
    result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin with id {plugin_id} not found"
        )
    
    if not plugin.enabled:
        return PluginDisableResponse(
            success=True,
            message=f"Plugin '{plugin.name}' is already disabled"
        )
    
    try:
        disable_result = await plugin_manager.disable_plugin(plugin_id, db)
        await db.commit()
        
        # Log audit
        await audit_service.log_action(
            db, current_user, "DISABLE", "plugin", plugin_id, plugin.name,
            {"version": plugin.version, "disabled_integrations": disable_result["disabled_integrations"]}, request
        )
        
        # Build message
        message = f"Plugin '{plugin.name}' disabled successfully"
        if disable_result["disabled_integrations"] > 0:
            message += f" ({disable_result['disabled_integrations']} integration(s) also disabled)"
        
        return PluginDisableResponse(
            success=disable_result["success"],
            message=message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable plugin: {str(e)}"
        )


@router.put("/{plugin_id}/config", response_model=PluginResponse)
@inject
async def update_plugin_config(
    plugin_id: int,
    config_update: PluginConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    plugin_manager: PluginManager = Depends(Provide[Container.plugin_manager]),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Update plugin configuration."""
    result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin with id {plugin_id} not found"
        )
    
    # TODO: Validate config against config_schema (JSON Schema validation)
    # For now, just update the config
    
    plugin.config = config_update.config
    await db.commit()
    await db.refresh(plugin)
    
    # If plugin is loaded, we need to reload it for config changes to take effect
    # For now, just update in DB. User can disable/enable to reload.
    
    # Log audit
    await audit_service.log_action(
        db, current_user, "UPDATE_CONFIG", "plugin", plugin_id, plugin.name,
        {"config": config_update.config}, request
    )
    
    return plugin


@router.delete("/{plugin_id}", response_model=PluginDeleteResponse)
@inject
async def delete_plugin(
    plugin_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    plugin_manager: PluginManager = Depends(Provide[Container.plugin_manager]),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Delete plugin from database (does not delete files)."""
    result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin with id {plugin_id} not found"
        )
    
    plugin_name = plugin.name
    
    # Unload plugin if it's loaded
    if plugin.loaded:
        await plugin_manager.unload_plugin(plugin_id, db)
    
    # Delete from database
    await db.delete(plugin)
    await db.commit()
    
    # Log audit
    await audit_service.log_action(
        db,
        current_user,
        "DELETE",
        "plugin",
        plugin_id,
        plugin_name,
        {},
        request
    )
    
    return PluginDeleteResponse(
        success=True,
        message=f"Plugin '{plugin_name}' removed from database (files not deleted)"
    )
