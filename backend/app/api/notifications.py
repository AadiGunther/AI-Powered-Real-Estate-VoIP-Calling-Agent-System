from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_maker
from app.models.notification import Notification, NotificationPreference, NotificationType
from app.models.user import User
from app.schemas.notification import (
    NotificationCreateRequest,
    NotificationListResponse,
    NotificationMarkReadResponse,
    NotificationPreferenceItem,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
    NotificationResponse,
)
from app.services.notification_realtime import register_connection, unregister_connection
from app.utils.logging import get_logger
from app.utils.security import decode_access_token, get_current_user


router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = get_logger("api.notifications")

_notification_rate_state = {}
_NOTIFICATION_RATE_WINDOW_SECONDS = 60.0
_NOTIFICATION_RATE_LIMIT = 120


async def notification_rate_limiter(current_user: User = Depends(get_current_user)) -> User:
    import time

    now = time.time()
    timestamps = _notification_rate_state.get(current_user.id, [])
    cutoff = now - _NOTIFICATION_RATE_WINDOW_SECONDS
    timestamps = [ts for ts in timestamps if ts >= cutoff]
    if len(timestamps) >= _NOTIFICATION_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for notifications.",
        )
    timestamps.append(now)
    _notification_rate_state[current_user.id] = timestamps
    return current_user


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: Optional[bool] = Query(None),
    type: Optional[NotificationType] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(notification_rate_limiter),
) -> NotificationListResponse:
    query = select(Notification).where(Notification.user_id == current_user.id)
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)
    if type is not None:
        query = query.where(Notification.type == type.value)
    if date_from is not None:
        query = query.where(Notification.created_at >= date_from)
    if date_to is not None:
        query = query.where(Notification.created_at <= date_to)
    count_query = select(Notification).where(Notification.user_id == current_user.id)
    if is_read is not None:
        count_query = count_query.where(Notification.is_read == is_read)
    if type is not None:
        count_query = count_query.where(Notification.type == type.value)
    if date_from is not None:
        count_query = count_query.where(Notification.created_at >= date_from)
    if date_to is not None:
        count_query = count_query.where(Notification.created_at <= date_to)
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Notification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.scalars().all()
    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_api(
    request: NotificationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationResponse:
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can create notifications.",
        )
    notification = Notification(
        user_id=request.user_id,
        message=request.message,
        type=request.type.value,
        is_read=False,
        related_lead_id=request.related_lead_id,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)
    return NotificationResponse.model_validate(notification)


@router.post("/{notification_id}/read", response_model=NotificationMarkReadResponse)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(notification_rate_limiter),
) -> NotificationMarkReadResponse:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    if not notification.is_read:
        notification.is_read = True
        await db.flush()
    return NotificationMarkReadResponse(success=True)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(notification_rate_limiter),
) -> None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    await db.delete(notification)
    await db.flush()


@router.get("/unread/count", response_model=int)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(notification_rate_limiter),
) -> int:
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .with_only_columns(Notification.id)
    )
    ids = result.scalars().all()
    return len(ids)


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferencesResponse:
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)
    )
    prefs = result.scalars().all()
    items = []
    existing = {p.notification_type: p.enabled for p in prefs}
    for nt in NotificationType:
        enabled = existing.get(nt.value, True)
        items.append(
            NotificationPreferenceItem(
                notification_type=nt,
                enabled=enabled,
            )
        )
    return NotificationPreferencesResponse(items=items)


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    request: NotificationPreferencesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferencesResponse:
    items = request.items
    for item in items:
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == current_user.id,
                NotificationPreference.notification_type == item.notification_type.value,
            )
        )
        pref = result.scalar_one_or_none()
        if pref:
            pref.enabled = item.enabled
        else:
            pref = NotificationPreference(
                user_id=current_user.id,
                notification_type=item.notification_type.value,
                enabled=item.enabled,
            )
            db.add(pref)
    await db.flush()
    return await get_preferences(db=db, current_user=current_user)


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    token_data = decode_access_token(token)
    if token_data is None:
        await websocket.close(code=1008)
        return
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.id == token_data.sub))
        user = result.scalar_one_or_none()
    if not user or not user.is_active:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    await register_connection(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await unregister_connection(user.id, websocket)
    except Exception:
        await unregister_connection(user.id, websocket)
        await websocket.close()

