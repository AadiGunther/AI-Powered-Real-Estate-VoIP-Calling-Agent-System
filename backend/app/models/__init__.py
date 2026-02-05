"""Models package initialization."""

from app.models.user import User, UserRole
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.lead import Lead, LeadQuality, LeadStatus, LeadSource
from app.models.call import Call, CallDirection, CallStatus, CallOutcome
from app.models.enquiry import Enquiry, EnquiryType

__all__ = [
    # User
    "User",
    "UserRole",
    # Property
    "Property",
    "PropertyType",
    "PropertyStatus",
    # Lead
    "Lead",
    "LeadQuality",
    "LeadStatus",
    "LeadSource",
    # Call
    "Call",
    "CallDirection",
    "CallStatus",
    "CallOutcome",
    # Enquiry
    "Enquiry",
    "EnquiryType",
]
