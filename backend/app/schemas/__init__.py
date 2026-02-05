"""Schemas package initialization."""

from app.schemas.auth import (
    Token,
    TokenPayload,
    TokenRefresh,
    LoginRequest,
    RegisterRequest,
    PasswordChangeRequest,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserRoleUpdate,
)
from app.schemas.property import (
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
    PropertyListResponse,
    PropertySearchParams,
)
from app.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadListResponse,
    LeadSearchParams,
    LeadQualityUpdate,
    LeadStatusUpdate,
    LeadAssign,
)
from app.schemas.call import (
    CallCreate,
    CallUpdate,
    CallResponse,
    CallListResponse,
    CallSearchParams,
    CallOutcomeUpdate,
    CallNotesUpdate,
    CallTranscript,
)

__all__ = [
    # Auth
    "Token",
    "TokenPayload",
    "TokenRefresh",
    "LoginRequest",
    "RegisterRequest",
    "PasswordChangeRequest",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "UserRoleUpdate",
    # Property
    "PropertyCreate",
    "PropertyUpdate",
    "PropertyResponse",
    "PropertyListResponse",
    "PropertySearchParams",
    # Lead
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadListResponse",
    "LeadSearchParams",
    "LeadQualityUpdate",
    "LeadStatusUpdate",
    "LeadAssign",
    # Call
    "CallCreate",
    "CallUpdate",
    "CallResponse",
    "CallListResponse",
    "CallSearchParams",
    "CallOutcomeUpdate",
    "CallNotesUpdate",
    "CallTranscript",
]
