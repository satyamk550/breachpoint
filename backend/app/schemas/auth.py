import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)


class RegisterRequest(Credentials):
    email: EmailStr


class LoginRequest(Credentials):
    pass


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    new_password: str = Field(min_length=10, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str
    created_at: datetime
    last_login_at: datetime | None


class ResetTokenResponse(BaseModel):
    user_id: uuid.UUID
    token: str
    expires_at: datetime
