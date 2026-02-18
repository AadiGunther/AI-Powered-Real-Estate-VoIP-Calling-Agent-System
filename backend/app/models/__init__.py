"""Models package initialization."""

from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit_log import AuditAction, AuditLog
from app.models.call import Call, CallDirection, CallOutcome, CallStatus
from app.models.elevenlabs_event_log import ElevenLabsEventLog
from app.models.enquiry import Enquiry, EnquiryType
from app.models.lead import Lead, LeadQuality, LeadSource, LeadStatus
from app.models.notification import Notification, NotificationPreference, NotificationType
from app.models.property import Property, PropertyStatus, PropertyType
from app.models.user import User, UserRole

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
    # Appointment
    "Appointment",
    "AppointmentStatus",
    # Enquiry
    "Enquiry",
    "EnquiryType",
    # Notification
    "Notification",
    "NotificationType",
    "NotificationPreference",
    # Audit
    "AuditLog",
    "AuditAction",
    # ElevenLabs
    "ElevenLabsEventLog",
]
