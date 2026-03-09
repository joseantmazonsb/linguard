from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.audit import AuditLog
from ..models.user import User
from ..schemas.audit import AuditLogResponse

router = APIRouter()


@router.get("/")
async def list_audit_logs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    action: str | None = Query(None, description="Filter by action (CREATE, UPDATE, DELETE, etc.)"),
    resource_type: str | None = Query(None, description="Filter by resource type (server, peer, etc.)"),
    resource_id: int | None = Query(None, description="Filter by resource ID"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    start_date: datetime | None = Query(None, description="Filter by start date"),
    end_date: datetime | None = Query(None, description="Filter by end date"),
    search: str | None = Query(None, description="Search in resource name and details"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List audit logs with filtering and pagination.

    Supports filtering by:
    - action: CREATE, UPDATE, DELETE, START, STOP, RELOAD, MIGRATE, etc.
    - resource_type: server, peer, backup, user, integration
    - resource_id: specific resource ID
    - user_id: who performed the action
    - date range: between start_date and end_date
    - search: text search in resource name and details
    """
    # Build query with filters
    query = select(AuditLog)

    filters = []

    if action:
        filters.append(AuditLog.action == action.upper())

    if resource_type:
        filters.append(AuditLog.resource_type == resource_type.lower())

    if resource_id is not None:
        filters.append(AuditLog.resource_id == resource_id)

    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)

    if start_date:
        filters.append(AuditLog.timestamp >= start_date)

    if end_date:
        filters.append(AuditLog.timestamp <= end_date)

    if search:
        search_pattern = f"%{search}%"
        # Search in multiple fields
        search_filters = [
            AuditLog.resource_name.ilike(search_pattern),
            AuditLog.action.ilike(search_pattern),
            AuditLog.resource_type.ilike(search_pattern),
            AuditLog.ip_address.ilike(search_pattern),
            AuditLog.error_message.ilike(search_pattern),
        ]
        
        # Add username search (join with User table)
        from ..models.user import User as UserModel
        query = query.join(UserModel, AuditLog.user_id == UserModel.id, isouter=True)
        search_filters.append(UserModel.username.ilike(search_pattern))
        
        filters.append(or_(*search_filters))

    if filters:
        query = query.where(and_(*filters))

    # Order by most recent first
    query = query.order_by(AuditLog.timestamp.desc())

    # Apply pagination
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    # Transform to frontend format
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "username": log.user.username if log.user else "Unknown",
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "resource_name": log.resource_name,
            "details": log.details,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "status": log.status,
            "error_message": log.error_message,
            "created_at": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific audit log entry by ID"""
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )

    return log


@router.get("/resource/{resource_type}/{resource_id}", response_model=list[AuditLogResponse])
async def get_resource_audit_history(
    resource_type: str,
    resource_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get complete audit history for a specific resource"""
    query = select(AuditLog).where(
        and_(
            AuditLog.resource_type == resource_type.lower(),
            AuditLog.resource_id == resource_id
        )
    ).order_by(AuditLog.timestamp.desc())

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return logs


@router.get("/user/{user_id}/actions", response_model=list[AuditLogResponse])
async def get_user_actions(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all actions performed by a specific user"""
    query = select(AuditLog).where(
        AuditLog.user_id == user_id
    ).order_by(AuditLog.timestamp.desc())

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return logs


@router.get("/stats/summary")
async def get_audit_summary(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get audit statistics summary.

    Returns counts by action type, resource type, and top users.
    """
    from sqlalchemy import func

    # Base query with optional date filtering
    base_filters = []
    if start_date:
        base_filters.append(AuditLog.timestamp >= start_date)
    if end_date:
        base_filters.append(AuditLog.timestamp <= end_date)

    # Count by action type
    action_query = select(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).group_by(AuditLog.action)

    if base_filters:
        action_query = action_query.where(and_(*base_filters))

    action_result = await db.execute(action_query)
    actions_by_type = {row[0]: row[1] for row in action_result.all()}

    # Count by resource type
    resource_query = select(
        AuditLog.resource_type,
        func.count(AuditLog.id).label('count')
    ).group_by(AuditLog.resource_type)

    if base_filters:
        resource_query = resource_query.where(and_(*base_filters))

    resource_result = await db.execute(resource_query)
    resources_by_type = {row[0]: row[1] for row in resource_result.all()}

    # Top users by activity
    user_query = select(
        AuditLog.user_id,
        func.count(AuditLog.id).label('count')
    ).group_by(AuditLog.user_id).order_by(func.count(AuditLog.id).desc()).limit(10)

    if base_filters:
        user_query = user_query.where(and_(*base_filters))

    user_result = await db.execute(user_query)
    top_users = [{"user_id": row[0], "action_count": row[1]} for row in user_result.all()]

    # Total count
    total_query = select(func.count(AuditLog.id))
    if base_filters:
        total_query = total_query.where(and_(*base_filters))

    total_result = await db.execute(total_query)
    total_count = total_result.scalar()

    return {
        "total_logs": total_count,
        "actions_by_type": actions_by_type,
        "resources_by_type": resources_by_type,
        "top_users": top_users,
        "date_range": {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None
        }
    }
