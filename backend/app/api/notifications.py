from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.containers import Container
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.user import User
from ..schemas.notification import NotificationCreate, NotificationResponse, NotificationUpdate
from ..services.notification_service import NotificationService

router = APIRouter()


@router.get("/", response_model=list[NotificationResponse])
@inject
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(Provide[Container.notification_service])
):
    """List notifications for the current user"""
    notifications = await notification_service.get_user_notifications(
        db, current_user.id, unread_only, limit, offset
    )
    return notifications


@router.get("/unread/count", response_model=dict)
@inject
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(Provide[Container.notification_service])
):
    """Get count of unread notifications for the current user"""
    count = await notification_service.get_unread_count(db, current_user.id)
    return {"count": count}


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_notification(
    notification_data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(Provide[Container.notification_service])
):
    """Create a new notification (admin only - for manual notifications)"""
    notification = await notification_service.create_notification(
        db=db,
        user_id=notification_data.user_id,
        title=notification_data.title,
        message=notification_data.message,
        type=notification_data.type,
        link=notification_data.link,
        event_type=notification_data.event_type,
        source_type=notification_data.source_type,
        source_id=notification_data.source_id
    )
    return notification


@router.put("/{notification_id}", response_model=NotificationResponse)
@inject
async def update_notification(
    notification_id: int,
    notification_data: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(Provide[Container.notification_service])
):
    """Mark a notification as read"""
    notification = await notification_service.mark_as_read(db, notification_id, current_user.id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return notification


@router.put("/read/all", response_model=dict)
@inject
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(Provide[Container.notification_service])
):
    """Mark all notifications as read for the current user"""
    count = await notification_service.mark_all_as_read(db, current_user.id)
    return {"marked_read": count}


@router.delete("/all", status_code=status.HTTP_200_OK, response_model=dict)
@inject
async def delete_all_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(Provide[Container.notification_service])
):
    """Delete all notifications for the current user"""
    count = await notification_service.delete_all_notifications(db, current_user.id)
    return {"deleted": count}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(Provide[Container.notification_service])
):
    """Delete a notification"""
    success = await notification_service.delete_notification(db, notification_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
