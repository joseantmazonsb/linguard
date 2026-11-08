import asyncio
import os
from typing import AsyncGenerator, Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import database
from ..core.database import get_db
from ..core.security import get_current_admin, get_current_user, get_settings_for_auth, security
from ..models.settings import GlobalSettings
from ..models.user import User

router = APIRouter()


async def get_log_file_path(db: AsyncSession = Depends(get_db)) -> str:
    """Get the configured log file path from database settings."""
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()
    
    if not settings or not settings.log_path:
        raise HTTPException(
            status_code=404, 
            detail="Log file path not configured. Please set log_path in system settings."
        )
    
    # Resolve relative paths to absolute
    log_path = settings.log_path
    if not os.path.isabs(log_path):
        log_path = os.path.abspath(log_path)
    
    return log_path


async def tail_log_file(
    file_path: str, lines: int = 100,
    authorized: Optional[Callable[[], Awaitable[bool]]] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream log file contents with live updates.
    First sends the last N lines, then streams new lines as they appear.
    """
    if authorized and not await authorized():
        return
    if not os.path.exists(file_path):
        yield f"data: Log file not found: {file_path}\n\n"
        return

    try:
        # First, send the last N lines
        with open(file_path, 'r') as f:
            # Read all lines and get the last N
            all_lines = f.readlines()
            initial_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            for line in initial_lines:
                if authorized and not await authorized():
                    return
                yield f"data: {line.rstrip()}\n\n"
        
        # Now stream new lines as they appear
        with open(file_path, 'r') as f:
            # Seek to end of file
            f.seek(0, os.SEEK_END)
            
            while True:
                if authorized and not await authorized():
                    return
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    # No new data, wait a bit
                    await asyncio.sleep(0.5)
                    
    except Exception as e:
        yield f"data: Error reading log file: {str(e)}\n\n"


@router.get("/stream")
async def stream_logs(
    lines: int = 100,
    log_path: str = Depends(get_log_file_path),
    current_user: User = Depends(get_current_admin),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream log file contents with Server-Sent Events (SSE).
    
    Args:
        lines: Number of initial lines to return (default: 100)
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    settings = await get_settings_for_auth(db)
    if not settings:
        raise HTTPException(status_code=503, detail="Application not configured")
    initial = (settings.setup_completed, settings.disable_auth, settings.auth_mode,
               settings.secret_key, settings.algorithm, current_user.id)

    async def authorized() -> bool:
        try:
            async with database.AsyncSessionLocal() as session:
                current = await get_settings_for_auth(session)
                if not current or (current.setup_completed, current.disable_auth, current.auth_mode,
                                   current.secret_key, current.algorithm) != initial[:5]:
                    return False
                if not (current.setup_completed and current.disable_auth):
                    if not credentials:
                        return False
                    jwt.decode(credentials.credentials, current.secret_key,
                               algorithms=[current.algorithm], options={"require_exp": True})
                user = await get_current_user(credentials, session)
                return user.id == initial[5] and user.role == "admin"
        except Exception:
            return False

    return StreamingResponse(
        tail_log_file(log_path, lines, authorized),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/download")
async def download_log_file(
    log_path: str = Depends(get_log_file_path),
    current_user: User = Depends(get_current_admin),
):
    """
    Download the complete log file.
    
    Returns:
        FileResponse with the log file
    """
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="Log file not found")
    
    return FileResponse(
        path=log_path,
        filename="linguard.log",
        media_type="text/plain",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/info")
async def get_log_info(
    log_path: str = Depends(get_log_file_path),
    current_user: User = Depends(get_current_admin),
):
    """
    Get information about the log file.
    
    Returns:
        Dict with file size, line count, and last modified time
    """
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="Log file not found")
    
    try:
        stat = os.stat(log_path)
        
        # Count lines
        with open(log_path, 'r') as f:
            line_count = sum(1 for _ in f)
        
        return {
            "path": log_path,
            "size_bytes": stat.st_size,
            "size_human": format_bytes(stat.st_size),
            "line_count": line_count,
            "last_modified": stat.st_mtime,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file info: {str(e)}")


def format_bytes(bytes: int) -> str:
    """Format bytes to human readable string."""
    size = float(bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"
