import hashlib
import hmac
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.call import Call, CallDirection, CallStatus
from app.utils.logging import get_logger
from app.utils.utils import clean_indian_number

router = APIRouter(prefix="/api", tags=["ElevenLabs Calls"])
logger = get_logger("api.elevenlabs_calls")


class StartCallRequest(BaseModel):
    phone: str = Field(..., description="Customer phone number")


class StartCallResponse(BaseModel):
    success: bool
    message: str
    call_data: Dict[str, Any]


class ElevenLabsCallError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def verify_elevenlabs_hmac(
    raw_body: bytes,
    timestamp: Optional[str],
    signature: Optional[str],
    secret: str,
) -> bool:
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    now = int(time.time())
    if abs(now - ts) > 300:
        return False
    message = f"{timestamp}.".encode("utf-8") + raw_body
    computed = hmac.new(
        key=secret.encode("utf-8"),
        msg=message,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


async def _start_elevenlabs_call(
    formatted_number: str,
    external_call_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not settings.elevenlabs_api_key:
        raise ElevenLabsCallError("ELEVENLABS_API_KEY is not configured.")
    if not settings.elevenlabs_agent_id:
        raise ElevenLabsCallError("ELEVENLABS_AGENT_ID is not configured.")
    if not settings.elevenlabs_agent_phone_number_id:
        raise ElevenLabsCallError("ELEVENLABS_AGENT_PHONE_NUMBER_ID is not configured.")

    url = "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "agent_id": settings.elevenlabs_agent_id,
        "agent_phone_number_id": settings.elevenlabs_agent_phone_number_id,
        "to_number": formatted_number,
    }

    if external_call_id:
        payload["conversation_initiation_client_data"] = {
            "type": "conversation_initiation_client_data",
            "dynamic_variables": {
                "call_sid": external_call_id,
                "external_call_id": external_call_id,
            },
        }

    timeout = httpx.Timeout(10.0, connect=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        logger.error("elevenlabs_call_request_failed", error=str(exc))
        raise ElevenLabsCallError("Failed to reach ElevenLabs service.") from exc

    try:
        data = response.json()
    except Exception:
        data = {}

    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        message = detail or f"ElevenLabs returned status {response.status_code}."
        logger.error(
            "elevenlabs_call_error",
            status_code=response.status_code,
            error_message=message,
            response=data,
        )
        raise ElevenLabsCallError(message, status_code=response.status_code)

    logger.info(
        "elevenlabs_call_started",
        to_number=formatted_number,
        response=data,
    )
    return data


@router.post("/call/start", response_model=StartCallResponse)
async def start_call(
    payload: StartCallRequest,
    db: AsyncSession = Depends(get_db),
) -> StartCallResponse:
    try:
        formatted_number = clean_indian_number(payload.phone)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    external_call_id = f"convai_{uuid.uuid4().hex}"

    db_call = Call(
        call_sid=external_call_id,
        direction=CallDirection.OUTBOUND.value,
        from_number=settings.twilio_phone_number,
        to_number=formatted_number,
        status=CallStatus.INITIATED.value,
        started_at=datetime.now(ZoneInfo("Asia/Kolkata")),
        handled_by_ai=True,
    )
    db.add(db_call)
    await db.commit()
    await db.refresh(db_call)

    logger.info(
        "elevenlabs_call_logged",
        call_id=db_call.id,
        call_sid=db_call.call_sid,
        from_number=db_call.from_number,
        to_number=db_call.to_number,
    )

    try:
        call_data = await _start_elevenlabs_call(formatted_number, external_call_id)
    except ElevenLabsCallError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        )

    return StartCallResponse(
        success=True,
        message="Call initiated successfully",
        call_data=call_data,
    )


@router.post("/webhook/elevenlabs")
async def elevenlabs_webhook(request: Request) -> Dict[str, bool]:
    raw_body = await request.body()
    signature = request.headers.get("X-EL-Signature")
    timestamp = request.headers.get("X-EL-Timestamp")

    if not settings.elevenlabs_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ELEVENLABS_WEBHOOK_SECRET is not configured.",
        )

    if not verify_elevenlabs_hmac(
        raw_body=raw_body,
        timestamp=timestamp,
        signature=signature,
        secret=settings.elevenlabs_webhook_secret,
    ):
        logger.warning("elevenlabs_webhook_invalid_signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    body = await request.json()

    event_type = body.get("event_type")
    call_id = body.get("call_id") or body.get("id")
    external_id = body.get("external_id")
    status_value = body.get("status")
    duration = body.get("duration_seconds") or body.get("duration")
    phone = (
        body.get("phone_number")
        or body.get("phone")
        or body.get("to_number")
        or body.get("from_number")
    )

    logger.info(
        "elevenlabs_webhook_event",
        event_type=event_type,
        call_id=call_id,
        external_id=external_id,
        status=status_value,
        duration=duration,
        phone=phone,
        raw=body,
    )

    return {"received": True}
