from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..models.settings import GlobalSettings
from .database import get_db

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer with auto_error=False to make it optional
security = HTTPBearer(auto_error=False)


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


async def create_access_token(data: dict, db: AsyncSession, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    settings = await get_settings_for_auth(db)
    
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application not configured. Please complete setup first."
        )
    
    to_encode = data.copy()
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
    
    # If settings don't exist yet, we're in setup mode - allow access to setup endpoints only
    # This is handled by route-level checks in setup.py
    
    if settings and settings.disable_auth:
        # Auth is disabled - return first user or create temp admin
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            return user
        
        # Create a temporary admin user if none exists
        from ..models.user import User as UserModel
        
        temp_user = UserModel(
            username="admin",
            email="admin@localhost",
            hashed_password=pwd_context.hash("temp")
        )
        db.add(temp_user)
        await db.commit()
        await db.refresh(temp_user)
        return temp_user
    
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
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user
