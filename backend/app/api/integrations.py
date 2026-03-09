import httpx
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.containers import Container
from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.security import get_current_user
from ..models.user import User
from ..schemas.integration import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationUpdate,
)
from ..services.audit_logger import AuditService
from ..services.integration_service import IntegrationService

router = APIRouter()


async def fetch_telegram_chat_id(bot_token: str) -> str:
    """
    Fetch the chat_id from Telegram bot using getUpdates API.
    Raises HTTPException if chat_id cannot be fetched.
    """
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid bot token: {data.get('description', 'Unknown error')}",
                )

            results = data.get("result", [])
            if not results:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot fetch chat ID. Please send a message to your bot first (e.g., /start) to initialize it, then try again.",
                )

            # Get chat_id from the most recent message
            chat_id = results[0].get("message", {}).get("chat", {}).get("id")
            if not chat_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not extract chat ID from bot messages. Please ensure the bot has received at least one message.",
                )

            return str(chat_id)

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to Telegram API: {str(e)}",
        )


@router.get("/", response_model=list[IntegrationResponse])
@inject
async def list_integrations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(
        Provide[Container.integration_service]
    ),
):
    """List all integrations"""
    integrations = await integration_service.get_integrations(db)
    return integrations


@router.get("/{integration_id}", response_model=IntegrationResponse)
@inject
async def get_integration(
    integration_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(
        Provide[Container.integration_service]
    ),
):
    """Get a specific integration by ID"""
    integration = await integration_service.get_integration(db, integration_id)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found"
        )
    return integration


@router.post(
    "/", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED
)
@inject
async def create_integration(
    integration_data: IntegrationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
    integration_service: IntegrationService = Depends(
        Provide[Container.integration_service]
    ),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Create a new integration"""
    from sqlalchemy import select
    from ..models.plugin import Plugin
    
    config = integration_data.config.copy() if integration_data.config else {}
    plugin_id = None

    # Handle plugin-based integrations
    if integration_data.type.startswith("plugin:"):
        module_name = integration_data.type.split(":", 1)[1]
        result = await db.execute(
            select(Plugin).where(Plugin.module_name == module_name)
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plugin '{module_name}' not found"
            )
        plugin_id = plugin.id

    # Auto-fetch chat_id for Telegram integrations
    if integration_data.type == "telegram":
        bot_token = config.get("bot_token")
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bot token is required for Telegram integration",
            )

        # Fetch chat_id from Telegram API
        chat_id = await fetch_telegram_chat_id(bot_token)
        config["chat_id"] = chat_id

    integration = await integration_service.create_integration(
        db=db,
        name=integration_data.name,
        type=integration_data.type,
        config=config,
        events_subscribed=integration_data.events_subscribed,
        description=integration_data.description,
        enabled=integration_data.enabled,
        plugin_id=plugin_id,
    )

    # Log audit event
    await audit_service.log_action(
        db,
        current_user,
        "CREATE",
        "integration",
        integration.id,
        integration.name,
        {"type": integration.type},
        request,
    )

    # Publish event
    await event_bus.publish(
        EventType.INTEGRATION_TRIGGERED,
        "integration",
        integration.id,
        {"action": "created", "name": integration.name},
        current_user.id,
    )

    return integration


@router.put("/{integration_id}", response_model=IntegrationResponse)
@inject
async def update_integration(
    integration_id: int,
    integration_data: IntegrationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
    integration_service: IntegrationService = Depends(
        Provide[Container.integration_service]
    ),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Update an integration"""
    # Check if this is the built-in In-App Notifications integration
    integration = await integration_service.get_integration(db, integration_id)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found"
        )

    # Prevent modification of name and restrict events_subscribed for In-App Notifications
    if integration.name == "In-App Notifications":
        # Prevent name changes
        if (
            integration_data.name is not None
            and integration_data.name != "In-App Notifications"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change the name of the built-in In-App Notifications integration",
            )

        # Prevent description changes
        if (
            integration_data.description is not None
            and integration_data.description != integration.description
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change the description of the built-in In-App Notifications integration",
            )

        # Validate events_subscribed - only allow the 3 specific events
        if integration_data.events_subscribed is not None:
            allowed_events = {
                EventType.SERVER_RELOADED.value,
                EventType.PEER_CONNECTED.value,
                EventType.PEER_DISCONNECTED.value,
            }
            invalid_events = set(integration_data.events_subscribed) - allowed_events
            if invalid_events:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"In-App Notifications can only subscribe to: {', '.join(sorted(allowed_events))}",
                )

    # Handle Telegram integration updates
    update_data = integration_data.model_dump(exclude_unset=True)
    if integration.type == "telegram" and "config" in update_data:
        config = update_data["config"]
        # If bot_token is being updated, fetch new chat_id
        if "bot_token" in config:
            bot_token = config["bot_token"]
            if not bot_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bot token is required for Telegram integration",
                )

            # Fetch new chat_id from Telegram API
            chat_id = await fetch_telegram_chat_id(bot_token)
            config["chat_id"] = chat_id
            update_data["config"] = config

    integration = await integration_service.update_integration(
        db, integration_id, **update_data
    )

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found"
        )

    # Log audit event
    await audit_service.log_action(
        db,
        current_user,
        "UPDATE",
        "integration",
        integration.id,
        integration.name,
        integration_data.model_dump(exclude_unset=True),
        request,
    )

    return integration


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_integration(
    integration_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
    integration_service: IntegrationService = Depends(
        Provide[Container.integration_service]
    ),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
):
    """Delete an integration"""
    integration = await integration_service.get_integration(db, integration_id)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found"
        )

    # Prevent deletion of the built-in In-App Notifications integration
    if integration.name == "In-App Notifications":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete the built-in In-App Notifications integration",
        )

    integration_name = integration.name
    success = await integration_service.delete_integration(db, integration_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete integration",
        )

    # Log audit event
    await audit_service.log_action(
        db,
        current_user,
        "DELETE",
        "integration",
        integration_id,
        integration_name,
        {},
        request,
    )


@router.get("/types/available", response_model=list[dict])
@inject
async def get_available_integration_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of available integration types and their configuration schemas"""
    from sqlalchemy import select
    from ..models.plugin import Plugin
    
    # Built-in integration types
    types = [
        {
            "type": "notification",
            "name": "In-App Notification",
            "description": "Display notifications in the notification center",
            "config_schema": {},
            "icon": "bell",
            "is_plugin": False,
            "enabled": True,
        },
        {
            "type": "webhook",
            "name": "Webhook",
            "description": "Send HTTP requests to external URLs",
            "config_schema": {
                "url": {
                    "type": "string",
                    "required": True,
                    "description": "Webhook URL",
                },
                "method": {
                    "type": "string",
                    "required": False,
                    "default": "POST",
                    "options": ["GET", "POST", "PUT"],
                },
                "headers": {
                    "type": "object",
                    "required": False,
                    "description": "Custom HTTP headers",
                },
            },
            "icon": "link",
            "is_plugin": False,
            "enabled": True,
        },
        {
            "type": "email",
            "name": "Email",
            "description": "Send email notifications",
            "config_schema": {
                "smtp_host": {"type": "string", "required": True},
                "smtp_port": {"type": "number", "required": True, "default": 587},
                "username": {"type": "string", "required": True},
                "password": {"type": "string", "required": True, "sensitive": True},
                "from": {"type": "string", "required": True},
                "to": {
                    "type": "array",
                    "required": True,
                    "description": "Recipient email addresses",
                },
            },
            "icon": "mail",
            "is_plugin": False,
            "enabled": True,
        },
        {
            "type": "slack",
            "name": "Slack",
            "description": "Send messages to Slack channels",
            "config_schema": {
                "webhook_url": {
                    "type": "string",
                    "required": True,
                    "sensitive": True,
                    "description": "Slack webhook URL",
                }
            },
            "icon": "slack",
            "is_plugin": False,
            "enabled": True,
        },
        {
            "type": "discord",
            "name": "Discord",
            "description": "Send messages to Discord channels",
            "config_schema": {
                "webhook_url": {
                    "type": "string",
                    "required": True,
                    "sensitive": True,
                    "description": "Discord webhook URL",
                }
            },
            "icon": "discord",
            "is_plugin": False,
            "enabled": True,
        },
        {
            "type": "telegram",
            "name": "Telegram",
            "description": "Send messages via Telegram bot",
            "config_schema": {
                "bot_token": {
                    "type": "string",
                    "required": True,
                    "sensitive": True,
                }
            },
            "icon": "telegram",
            "is_plugin": False,
            "enabled": True,
        },
        {
            "type": "script",
            "name": "Custom Script",
            "description": "Execute custom shell scripts",
            "config_schema": {
                "script_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to executable script",
                },
                "args": {
                    "type": "array",
                    "required": False,
                    "description": "Script arguments",
                },
            },
            "icon": "code",
            "is_plugin": False,
            "enabled": True,
        },
    ]
    
    # Add discovered plugins as integration types
    result = await db.execute(select(Plugin))
    plugins = result.scalars().all()
    
    for plugin in plugins:
        types.append({
            "type": f"plugin:{plugin.module_name}",
            "name": plugin.name,
            "description": plugin.description or f"Custom plugin: {plugin.name}",
            "config_schema": plugin.config_schema or {},
            "icon": "puzzle",  # Plugin icon
            "is_plugin": True,
            "plugin_id": plugin.id,
            "plugin_version": plugin.version,
            "plugin_author": plugin.author,
            "enabled": plugin.enabled,
        })
    
    return types
