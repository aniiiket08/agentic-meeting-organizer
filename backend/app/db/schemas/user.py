from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr
from app.db.models.user import UserRole


class UserBase(BaseModel):
    name: str
    username: str
    email: EmailStr
    role: UserRole = UserRole.STUDENT


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserDirectoryEntry(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """Login payload. The `username` field accepts either a username or an email."""
    username: str
    password: str