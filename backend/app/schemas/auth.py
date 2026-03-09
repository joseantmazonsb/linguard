from pydantic import BaseModel, EmailStr, field_validator

from ..utils.validation import validate_username, validate_password


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator('username')
    @classmethod
    def validate_username_field(cls, v):
        return validate_username(v, field_name="Username")

    @field_validator('password')
    @classmethod
    def validate_password_field(cls, v):
        return validate_password(v, field_name="Password")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True


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
