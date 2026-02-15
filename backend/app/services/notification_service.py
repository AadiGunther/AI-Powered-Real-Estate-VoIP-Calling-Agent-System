from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
)
from app.services.notification_realtime import send_notification


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _is_enabled(self, user_id: int, notification_type: NotificationType) -> bool:
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type.value,
            )
        )
        pref = result.scalar_one_or_none()
        if pref is None:
            return True
        return pref.enabled

    async def create_notification(
        self,
        user_id: int,
        message: str,
        notification_type: NotificationType,
        related_lead_id: Optional[int] = None,
    ) -> Optional[Notification]:
        enabled = await self._is_enabled(user_id, notification_type)
        if not enabled:
            return None
        notification = Notification(
            user_id=user_id,
            message=message,
            type=notification_type.value,
            is_read=False,
            related_lead_id=related_lead_id,
        )
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        await send_notification(
            user_id,
            {
                "id": notification.id,
                "user_id": notification.user_id,
                "message": notification.message,
                "type": notification.type,
                "is_read": notification.is_read,
                "related_lead_id": notification.related_lead_id,
                "created_at": notification.created_at.isoformat(),
            },
        )
        return notification

