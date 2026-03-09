from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.exceptions import ValidationError
from ..core.security import create_access_token, get_current_user, get_password_hash, verify_password
from ..models.user import User
from ..schemas.auth import PasswordChange, Token, UserCreate, UserProfileUpdate, UserResponse

router = APIRouter()


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
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

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise ValidationError(
            "username",
            "Username already registered"
        )

    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise ValidationError(
            "email",
            "Email already registered"
        )

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password)
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return user


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
