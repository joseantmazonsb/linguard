from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator

from ..utils.validation import validate_password


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str = "admin"
    auth_provider: str = "local"

    class Config:
        from_attributes = True


class LoginResponse(Token):
    user: UserResponse


class UserProfileUpdate(BaseModel):
    email: EmailStr


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator('current_password')
    @classmethod
    def validate_current_password_field(cls, v):
        return validate_password(v, field_name="Current password")

    @field_validator('new_password')
    @classmethod
    def validate_new_password_field(cls, v):
        return validate_password(v, field_name="New password")


class UserAdminUpdate(BaseModel):
    """Fields an admin can change on another user."""
    role: Literal["admin", "standard"]


class OIDCConfigResponse(BaseModel):
    """Public info the login page needs to render SSO options."""
    oidc_enabled: bool
    auth_mode: str
    provider_name: str | None = None


class OIDCCallbackRequest(BaseModel):
    code: str
    state: str


class OIDCTestRequest(BaseModel):
    discovery_url: str
    client_id: str
    client_secret: str
    scopes: str = "openid email profile"


class OIDCTestResponse(BaseModel):
    success: bool
    provider_name: str | None = None
    message: str
