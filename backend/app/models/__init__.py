"""Models package initialization."""

from app.models.user import User, UserRole
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.lead import Lead, LeadQuality, LeadStatus, LeadSource
from app.models.call import Call, CallDirection, CallStatus, CallOutcome
from app.models.enquiry import Enquiry, EnquiryType
from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import Notification, NotificationType, NotificationPreference
from app.models.audit_log import AuditLog, AuditAction
from app.models.elevenlabs_event_log import ElevenLabsEventLog

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
