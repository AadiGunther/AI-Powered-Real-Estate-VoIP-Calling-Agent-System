from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, field_validator

from app.models.notification import NotificationType
from app.utils.logging import get_logger


_ist_tz = ZoneInfo("Asia/Kolkata")
_notification_schema_logger = get_logger("schemas.notification")


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    message: str
    type: NotificationType
    is_read: bool
    related_lead_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator("created_at", mode="after")
    @classmethod
    def to_ist(cls, v: datetime, info) -> datetime:
        original = v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        ist_value = v.astimezone(_ist_tz)
        try:
            _notification_schema_logger.info(
                "notification_datetime_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    total: int
    page: int
    page_size: int


class NotificationCreateRequest(BaseModel):
    user_id: int
    message: str
    type: NotificationType
    related_lead_id: Optional[int] = None


class NotificationMarkReadResponse(BaseModel):
    success: bool


class NotificationPreferenceItem(BaseModel):
    notification_type: NotificationType
    enabled: bool


class NotificationPreferencesResponse(BaseModel):
    items: List[NotificationPreferenceItem]


class NotificationPreferencesUpdateRequest(BaseModel):
    items: List[NotificationPreferenceItem]
