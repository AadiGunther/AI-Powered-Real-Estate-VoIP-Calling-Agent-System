"""User schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.AGENT


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None


class UserRoleUpdate(BaseModel):
    """Schema for updating user role."""
    role: UserRole


class UserManagerAssign(BaseModel):
    """Schema for assigning manager to agent."""
    manager_id: int


class UserResponse(UserBase):
    """User response schema."""
    id: int
    role: str
    is_active: bool
    is_verified: bool
    manager_id: Optional[int] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response."""
    users: list[UserResponse]
    total: int
    page: int
    page_size: int
