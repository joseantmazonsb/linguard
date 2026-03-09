import os
import tempfile

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.containers import Container
from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.security import get_current_user
from ..models.backup import Backup
from ..models.user import User
from ..schemas.backup import BackupCreate, BackupResponse
from ..services.audit_logger import AuditService
from ..services.backup_service import BackupService

router = APIRouter()


@router.get("/")
async def list_backups(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all backups"""
    query = select(Backup).order_by(Backup.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    backups = result.scalars().all()

    # Transform to frontend format
    return [
        {
            "id": b.id,
            "filename": b.filename,
            "description": b.description,
            "file_size": b.size_bytes,
            "is_encrypted": b.is_encrypted,
            "servers_count": b.servers_count,
            "peers_count": b.peers_count,
            "created_by_id": b.created_by_user_id,
            "created_by_username": b.created_by.username if b.created_by else "Unknown",
            "created_at": b.created_at.isoformat(),
        }
        for b in backups
    ]


@router.get("/{backup_id}", response_model=BackupResponse)
async def get_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific backup by ID"""
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found"
        )

    return backup


@router.post("/", status_code=status.HTTP_201_CREATED)
@inject
async def create_backup(
    backup_data: BackupCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    backup_service: BackupService = Depends(Provide[Container.backup_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """
    Create a new backup of all configurations.

    Includes:
    - Global settings
    - All servers
    - All peers
    - Relationships and configurations
    """
    try:
        backup = await backup_service.create_backup(
            db=db,
            user_id=current_user.id,
            description=backup_data.description,
        )

        # Log audit event
        await audit_service.log_action(
            db, current_user, "CREATE", "backup", backup.id,
            f"Backup-{backup.created_at.strftime('%Y%m%d-%H%M%S')}",
            {"description": backup.description, "encrypted": backup.is_encrypted}, request
        )

        # Publish event
        await event_bus.publish(
            EventType.BACKUP_CREATED,
            "backup",
            backup.id,
            {"description": backup.description, "size": backup.size_bytes},
            current_user.id
        )

        return {
            "id": backup.id,
            "filename": backup.filename,
            "description": backup.description,
            "file_size": backup.size_bytes,
            "is_encrypted": backup.is_encrypted,
            "servers_count": backup.servers_count,
            "peers_count": backup.peers_count,
            "created_by_id": backup.created_by_user_id,
            "created_by_username": backup.created_by.username if backup.created_by else "Unknown",
            "created_at": backup.created_at.isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup: {e!s}"
        ) from e


@router.post("/{backup_id}/restore")
@inject
async def restore_backup(
    backup_id: int,
    request: Request,
    passphrase: str | None = None,
    overwrite: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    backup_service: BackupService = Depends(Provide[Container.backup_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """
    Restore from a backup.

    Args:
        backup_id: Backup to restore
        passphrase: Decryption passphrase if backup is encrypted
        overwrite: Whether to overwrite existing configurations
    """
    # Get backup
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found"
        )

    if backup.is_encrypted and not passphrase:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passphrase required for encrypted backup"
        )

    try:
        result = await backup_service.restore_backup(
            db=db,
            backup_id=backup_id,
            user_id=current_user.id,
            passphrase=passphrase,
            clear_existing=overwrite
        )

        # Log audit event
        await audit_service.log_action(
            db, current_user, "RESTORE", "backup", backup.id,
            f"Backup-{backup.created_at.strftime('%Y%m%d-%H%M%S')}",
            {"overwrite": overwrite, "result": result}, request
        )

        # Publish event
        await event_bus.publish(
            EventType.BACKUP_RESTORED,
            "backup",
            backup.id,
            {"description": backup.description, "overwrite": overwrite},
            current_user.id
        )

        return {
            "success": True,
            "message": "Backup restored successfully",
            "details": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore backup: {e!s}"
        ) from e


@router.get("/{backup_id}/download")
@inject
async def download_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings_service = Depends(Provide[Container.settings_service])
):
    """Download a backup file"""
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found"
        )

    backup_dir = await settings_service.get_backup_dir(db)
    file_path = os.path.join(backup_dir, backup.filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup file not found on disk"
        )

    filename = f"wireguard-backup-{backup.created_at.strftime('%Y%m%d-%H%M%S')}.json"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/json"
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
@inject
async def upload_backup(
    file: UploadFile,
    request: Request,
    description: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    backup_service: BackupService = Depends(Provide[Container.backup_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Upload and import a backup file"""
    temp_path = None
    try:
        # Read uploaded file
        content = await file.read()

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.json') as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        # Import backup
        backup = await backup_service.import_backup(
            db=db,
            file_path=temp_path,
            user_id=current_user.id,
            description=description or f"Imported from {file.filename}"
        )

        # Log audit event
        await audit_service.log_action(
            db, current_user, "IMPORT", "backup", backup.id,
            f"Backup-{backup.created_at.strftime('%Y%m%d-%H%M%S')}",
            {"filename": file.filename, "description": backup.description}, request
        )

        return {
            "id": backup.id,
            "filename": backup.filename,
            "description": backup.description,
            "file_size": backup.size_bytes,
            "is_encrypted": backup.is_encrypted,
            "servers_count": backup.servers_count,
            "peers_count": backup.peers_count,
            "created_by_id": backup.created_by_user_id,
            "created_by_username": backup.created_by.username if backup.created_by else "Unknown",
            "created_at": backup.created_at.isoformat(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid backup file: {e!s}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload backup: {e!s}"
        ) from e
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@router.delete("/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_backup(
    backup_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
    settings_service = Depends(Provide[Container.settings_service])
):
    """Delete a backup"""
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()

    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup not found"
        )

    backup_name = f"Backup-{backup.created_at.strftime('%Y%m%d-%H%M%S')}"
    
    backup_dir = await settings_service.get_backup_dir(db)
    file_path = os.path.join(backup_dir, backup.filename)

    # Delete from database
    await db.delete(backup)
    await db.commit()

    # Delete file from disk
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
        except Exception as e:
            print(f"Warning: Failed to delete backup file: {e}")

    # Log audit event
    await audit_service.log_action(
        db, current_user, "DELETE", "backup", backup_id, backup_name,
        {"file_path": file_path}, request
    )

    # Publish event
    await event_bus.publish(
        EventType.BACKUP_DELETED,
        "backup",
        backup_id,
        {"description": backup.description},
        current_user.id
    )

    return None


@router.get("/stats/summary")
async def get_backup_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get backup statistics"""
    from sqlalchemy import func

    # Total backups
    total_query = select(func.count(Backup.id))
    total_result = await db.execute(total_query)
    total_count = total_result.scalar()

    # Total size
    size_query = select(func.sum(Backup.size_bytes))
    size_result = await db.execute(size_query)
    total_size = size_result.scalar() or 0

    # Latest backup
    latest_query = select(Backup).order_by(Backup.created_at.desc()).limit(1)
    latest_result = await db.execute(latest_query)
    latest_backup = latest_result.scalar_one_or_none()

    # Encrypted count
    encrypted_query = select(func.count(Backup.id)).where(Backup.is_encrypted == True)
    encrypted_result = await db.execute(encrypted_query)
    encrypted_count = encrypted_result.scalar()

    # Get oldest backup
    oldest_query = select(Backup).order_by(Backup.created_at.asc()).limit(1)
    oldest_result = await db.execute(oldest_query)
    oldest_backup = oldest_result.scalar_one_or_none()

    return {
        "total_backups": total_count,
        "total_size": total_size,  # Changed from total_size_bytes
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "encrypted_backups": encrypted_count,
        "latest_backup": {
            "id": latest_backup.id,
            "created_at": latest_backup.created_at.isoformat(),
            "description": latest_backup.description
        } if latest_backup else None,
        "oldest_backup": {
            "id": oldest_backup.id,
            "created_at": oldest_backup.created_at.isoformat(),
            "description": oldest_backup.description
        } if oldest_backup else None
    }
