"""Schemas package initialization."""

from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    Token,
    TokenPayload,
    TokenRefresh,
)
from app.schemas.call import (
    CallCreate,
    CallListResponse,
    CallNotesUpdate,
    CallOutcomeUpdate,
    CallResponse,
    CallSearchParams,
    CallTranscript,
    CallUpdate,
)
from app.schemas.lead import (
    LeadAssign,
    LeadCreate,
    LeadListResponse,
    LeadQualityUpdate,
    LeadResponse,
    LeadSearchParams,
    LeadStatusUpdate,
    LeadUpdate,
)
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.schemas.property import (
    PropertyCreate,
    PropertyListResponse,
    PropertyResponse,
    PropertySearchParams,
    PropertyUpdate,
)
from app.schemas.user import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
    UserUpdate,
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
    # Product
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductListResponse",
    # Lead
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadListResponse",
    "LeadSearchParams",
    "LeadQualityUpdate",
    "LeadStatusUpdate",
    "LeadAssign",
    "LeadBulkAssign",
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
