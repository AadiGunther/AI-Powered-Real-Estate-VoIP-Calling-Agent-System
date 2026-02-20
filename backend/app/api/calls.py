"""Calls API endpoints."""

import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from twilio.base.exceptions import TwilioRestException
    from twilio.rest import Client as TwilioClient
except ImportError:
    TwilioRestException = Exception
    TwilioClient = None

from app.config import settings
from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.call import Call, CallDirection, CallStatus
from app.models.enquiry import Enquiry, EnquiryType
from app.models.lead import Lead, LeadQuality, LeadSource, LeadStatus
from app.models.notification import NotificationType
from app.models.user import User, UserRole
from app.schemas.call import (
    CallListResponse,
    CallNotesUpdate,
    CallOutcomeUpdate,
    CallResponse,
    CallTranscript,
    DialRequest,
    TranscriptMessage,
)
from app.services.blob_service import BlobService
from app.services.notification_service import NotificationService
from app.utils.logging import get_logger
from app.utils.security import get_current_user
from app.utils.utils import clean_indian_number

router = APIRouter()

_elevenlabs_rate_state: Dict[str, list[float]] = {}
_ELEVENLABS_RATE_WINDOW_SECONDS = 60.0
_ELEVENLABS_RATE_LIMIT = 60


async def verify_elevenlabs_api_key(x_api_key: str = Header(..., alias="x-api-key")) -> str:
    if not settings.elevenlabs_tools_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ElevenLabs tools API key is not configured.",
        )
    if x_api_key != settings.elevenlabs_tools_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ElevenLabs tools API key.",
        )
    now = time.time()
    timestamps = _elevenlabs_rate_state.get(x_api_key, [])
    cutoff = now - _ELEVENLABS_RATE_WINDOW_SECONDS
    timestamps = [ts for ts in timestamps if ts >= cutoff]
    if len(timestamps) >= _ELEVENLABS_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for ElevenLabs tools API.",
        )
    timestamps.append(now)
    _elevenlabs_rate_state[x_api_key] = timestamps
    return x_api_key


class ElevenLabsDialRequest(BaseModel):
    caller_id: str
    recipient_number: str
    voice_id: str


@router.post("/dial", response_model=CallResponse)
async def dial_number(
    request: DialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Call:
    """Initiate an outbound call."""
    try:
        if TwilioClient is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Twilio is not available on this server.",
            )
        if not settings.enable_existing_outbound_flow:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Existing outbound Twilio call flow is disabled by configuration.",
            )
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Twilio credentials are not configured.",
            )

        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        
        # Use TwiML App SID if configured, otherwise fallback to direct URL
        call_kwargs = {
            "to": request.to_number,
            "from_": settings.twilio_phone_number,
            "status_callback": f"{settings.base_url}/twilio/call-status",
            "status_callback_event": ["initiated", "ringing", "answered", "completed"],
            "status_callback_method": "POST",
            "record": True,
            "recording_status_callback": f"{settings.base_url}/twilio/recording-status",
            "recording_status_callback_method": "POST",
        }
        
        if settings.twilio_application_sid:
            call_kwargs["application_sid"] = settings.twilio_application_sid
        else:
            # Construct webhook URL for TwiML fallback
            webhook_url = f"{settings.base_url}/twilio/outbound-webhook"
            if request.lead_id:
                webhook_url += f"?lead_id={request.lead_id}"
            call_kwargs["url"] = webhook_url
            call_kwargs["method"] = "POST"
            
        call = client.calls.create(**call_kwargs)
        
        # Create call record
        db_call = Call(
            call_sid=call.sid,
            from_number=settings.twilio_phone_number,
            to_number=request.to_number,
            direction=CallDirection.OUTBOUND.value,
            status=CallStatus.INITIATED.value,
            started_at=datetime.now(ZoneInfo("Asia/Kolkata")),
            handled_by_ai=True,
            lead_id=request.lead_id
        )
        
        db.add(db_call)
        await db.commit()
        await db.refresh(db_call)
        
        return db_call
        
    except TwilioRestException as e:
        logger = get_logger("api.calls")
        logger.error("twilio_error", code=e.code, msg=e.msg, status=e.status)
        
        if e.code == 21219:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Twilio Trial Account Restriction: The destination number is not verified. "
                    "Please verify the number in your Twilio console or upgrade your account."
                ),
            )
        elif e.code == 21214:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number: The 'To' number is not a valid mobile number."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Twilio Error ({e.code}): {e.msg}"
            )
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate call: {str(e)}"
        )


@router.get("/", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    direction: Optional[str] = None,
    status: Optional[str] = None,
    outcome: Optional[str] = None,
    handled_by_ai: Optional[bool] = None,
    escalated: Optional[bool] = None,
    from_number: Optional[str] = None,
    lead_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CallListResponse:
    """List calls with optional filters."""
    logger = get_logger("api.calls")
    query = select(Call)
    
    logger.info(
        "list_calls_requested",
        role=current_user.role,
        page=page,
        page_size=page_size,
        direction=direction,
        status=status,
        outcome=outcome,
        handled_by_ai=handled_by_ai,
        escalated=escalated,
        from_number=from_number,
        lead_id=lead_id,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
    )
    
    # Apply filters
    if direction:
        query = query.where(Call.direction == direction)
    if status:
        query = query.where(Call.status == status)
    if outcome:
        query = query.where(Call.outcome == outcome)
    if handled_by_ai is not None:
        query = query.where(Call.handled_by_ai == handled_by_ai)
    if escalated is not None:
        query = query.where(Call.escalated_to_human == escalated)
    if from_number:
        query = query.where(Call.from_number.contains(from_number))
    if lead_id is not None:
        query = query.where(Call.lead_id == lead_id)
    if date_from:
        query = query.where(Call.created_at >= date_from)
    if date_to:
        query = query.where(Call.created_at <= date_to)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Call.created_at.desc())
    
    result = await db.execute(query)
    calls = result.scalars().all()
    
    logger.info(
        "list_calls_result",
        total=total,
        returned=len(calls),
    )
    
    return CallListResponse(
        calls=[CallResponse.model_validate(call) for call in calls],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/recordings", response_model=CallListResponse)
async def list_recordings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CallListResponse:
    """List calls that have stored recordings (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access call recordings",
        )

    base_query = select(Call).where(Call.recording_url.is_not(None))
    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        base_query.order_by(Call.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    calls = result.scalars().all()

    logger = get_logger("api.calls")
    logger.info(
        "list_recordings_result",
        total=total,
        returned=len(calls),
    )

    return CallListResponse(
        calls=[CallResponse.model_validate(call) for call in calls],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Call:
    """Get call details by ID."""
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )
    
    return call


@router.get("/{call_id}/recording")
async def get_call_recording(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get short-lived SAS recording URL (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access call recordings",
        )
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )
    
    if not call.recording_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not available for this call",
        )

    blob_service = BlobService()

    def _extract_container_and_blob_name(url: str) -> tuple[Optional[str], Optional[str]]:
        cleaned = str(url or "").strip().strip("`").strip().replace("`", "")
        if not cleaned:
            return None, None
        parsed = urlparse(cleaned)
        path = parsed.path.lstrip("/")
        if not path or "/" not in path:
            return None, None
        container, blob_name = path.split("/", 1)
        return (container or None), (blob_name or None)

    def _derive_elevenlabs_blob_name() -> Optional[str]:
        call_sid = str(call.call_sid or "").strip()
        match = re.search(r"(\d{10,13})$", call_sid)
        if not match:
            return None
        raw = match.group(1)
        ts = int(raw)
        event_ts = ts // 1000 if len(raw) == 13 else ts

        dt = call.started_at or call.ended_at or datetime.now(ZoneInfo("Asia/Kolkata"))
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        dt = dt.astimezone(ZoneInfo("Asia/Kolkata"))
        date_prefix = dt.strftime("%Y-%m-%d")
        return f"elevenlabs/{date_prefix}/{call_sid}_{event_ts}.mp3"

    def _candidate_date_prefixes() -> list[str]:
        tz = ZoneInfo("Asia/Kolkata")
        dates: list[str] = []
        for dt in [call.started_at, call.ended_at, datetime.now(tz)]:
            if dt is None:
                continue
            if getattr(dt, "tzinfo", None) is None:
                dt = dt.replace(tzinfo=tz)
            dt = dt.astimezone(tz)
            dates.append(dt.strftime("%Y-%m-%d"))
        if dates:
            try:
                d0 = datetime.strptime(dates[0], "%Y-%m-%d")
                dates.append((d0.replace(tzinfo=tz) - timedelta(days=1)).strftime("%Y-%m-%d"))
            except Exception:
                pass
        unique_dates = list(dict.fromkeys([d for d in dates if d]))
        return [f"elevenlabs/{d}/" for d in unique_dates]

    candidates: list[str] = []
    from_url = blob_service.generate_sas_from_blob_url(call.recording_url, expiry_minutes=15)
    if from_url:
        candidates.append(from_url)

    container_from_url, blob_name_from_url = _extract_container_and_blob_name(call.recording_url)
    if container_from_url and blob_name_from_url:
        direct_from_url = blob_service.generate_sas_for_blob(
            container_from_url,
            blob_name_from_url,
            expiry_minutes=15,
        )
        if direct_from_url:
            candidates.append(direct_from_url)

    derived_blob = _derive_elevenlabs_blob_name()
    if derived_blob:
        for container_candidate in [
            (blob_service.container_name or "").strip() or None,
            (container_from_url or "").strip() or None,
        ]:
            if not container_candidate:
                continue
            derived_url = blob_service.generate_sas_for_blob(
                container_candidate,
                derived_blob,
                expiry_minutes=15,
            )
            if derived_url:
                candidates.append(derived_url)

    call_sid_value = str(call.call_sid or "").strip()
    if call_sid_value and blob_service.client:
        prefixes = _candidate_date_prefixes()
        container_candidates = list(
            dict.fromkeys(
                [
                    (blob_service.container_name or "").strip(),
                    (container_from_url or "").strip(),
                ]
            )
        )
        for container_candidate in [c for c in container_candidates if c]:
            found_blob = await asyncio.to_thread(
                blob_service.find_latest_blob_name,
                prefixes,
                call_sid_value,
                container_candidate,
            )
            if found_blob:
                searched_url = blob_service.generate_sas_for_blob(
                    container_candidate,
                    found_blob,
                    expiry_minutes=15,
                )
                if searched_url:
                    candidates.append(searched_url)

    resolved_url: Optional[str] = None
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for candidate in candidates:
            cleaned = str(candidate).strip().strip("`").strip().replace("`", "")
            try:
                resp = await client.get(cleaned, headers={"Range": "bytes=0-0"})
            except Exception:
                continue
            if 200 <= resp.status_code < 300:
                resolved_url = cleaned
                break

    if not resolved_url:
        container_candidates = list(
            dict.fromkeys(
                [
                    (blob_service.container_name or "").strip(),
                    (container_from_url or "").strip(),
                ]
            )
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recording not found in storage (containers tried: {', '.join([c for c in container_candidates if c])})",
        )

    return {
        "call_id": call.id,
        "call_sid": call.call_sid,
        "recording_url": resolved_url,
        "duration": call.recording_duration,
    }


@router.get("/{call_id}/recording-url")
async def get_call_recording_url(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the SAS URL for a call recording."""
    logger = get_logger("api.calls")
    logger.info(f"get_call_recording_url call_id={call_id} user={current_user.email}")

    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    
    if not call or not call.recording_url:
        logger.warning(f"get_call_recording_url_not_found call_id={call_id}")
        raise HTTPException(status_code=404, detail="Recording not found")

    blob_service = BlobService()
    
    # 1. Try direct URL first (fastest)
    plain_url = await blob_service.check_blob_exists(call.recording_url)
    resolved_url = None

    if plain_url:
        resolved_url = blob_service.generate_sas_from_blob_url(plain_url)
    
    # 2. Fallback to robust search if not found
    if not resolved_url:
        call_sid = str(call.call_sid or "").strip()
        match = re.search(r"(\d{10,13})$", call_sid)
        if match:
            raw = match.group(1)
            ts = int(raw)
             
            tz = ZoneInfo("Asia/Kolkata")
            dates = []
            for dt in [call.started_at, call.ended_at, datetime.now(tz)]:
                if dt:
                    if getattr(dt, "tzinfo", None) is None:
                        dt = dt.replace(tzinfo=tz)
                    dates.append(dt.astimezone(tz).strftime("%Y-%m-%d"))
             
            unique_dates = list(dict.fromkeys(dates))
            prefixes = [f"elevenlabs/{d}/" for d in unique_dates]
            
            found_blob = await asyncio.to_thread(
                blob_service.find_latest_blob_name,
                prefixes,
                call_sid,
                blob_service.container_name,
            )
            if found_blob:
                resolved_url = blob_service.generate_sas_for_blob(blob_service.container_name, found_blob)

    if not resolved_url:
        logger.error(f"get_call_recording_url_failed call_id={call_id}")
        raise HTTPException(status_code=404, detail="Recording not found in storage")

    return {"recording_url": resolved_url}


@router.get("/{call_id}/recording/stream")
async def stream_call_recording(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Proxy stream audio from Azure to the browser to bypass CORS/Private access."""
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    
    if not call or not call.recording_url:
        raise HTTPException(status_code=404, detail="Recording not found")

    blob_service = BlobService()

    def _extract_container_and_blob_name(url: str) -> tuple[Optional[str], Optional[str]]:
        cleaned = str(url or "").strip().strip("`").strip().replace("`", "")
        if not cleaned:
            return None, None
        parsed = urlparse(cleaned)
        path = parsed.path.lstrip("/")
        if not path or "/" not in path:
            return None, None
        container, blob_name = path.split("/", 1)
        return (container or None), (blob_name or None)

    def _derive_elevenlabs_blob_name() -> Optional[str]:
        call_sid = str(call.call_sid or "").strip()
        match = re.search(r"(\d{10,13})$", call_sid)
        if not match:
            return None
        raw = match.group(1)
        ts = int(raw)
        event_ts = ts // 1000 if len(raw) == 13 else ts

        dt = call.started_at or call.ended_at or datetime.now(ZoneInfo("Asia/Kolkata"))
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        dt = dt.astimezone(ZoneInfo("Asia/Kolkata"))
        date_prefix = dt.strftime("%Y-%m-%d")
        return f"elevenlabs/{date_prefix}/{call_sid}_{event_ts}.mp3"

    def _candidate_date_prefixes() -> list[str]:
        tz = ZoneInfo("Asia/Kolkata")
        dates: list[str] = []
        for dt in [call.started_at, call.ended_at, datetime.now(tz)]:
            if dt is None:
                continue
            if getattr(dt, "tzinfo", None) is None:
                dt = dt.replace(tzinfo=tz)
            dt = dt.astimezone(tz)
            dates.append(dt.strftime("%Y-%m-%d"))
        if dates:
            try:
                d0 = datetime.strptime(dates[0], "%Y-%m-%d")
                dates.append((d0.replace(tzinfo=tz) - timedelta(days=1)).strftime("%Y-%m-%d"))
            except Exception:
                pass
        unique_dates = list(dict.fromkeys([d for d in dates if d]))
        return [f"elevenlabs/{d}/" for d in unique_dates]

    candidates: list[str] = []
    from_url = blob_service.generate_sas_from_blob_url(call.recording_url)
    if from_url:
        candidates.append(from_url)

    container_from_url, blob_name_from_url = _extract_container_and_blob_name(call.recording_url)
    if container_from_url and blob_name_from_url:
        direct_from_url = blob_service.generate_sas_for_blob(container_from_url, blob_name_from_url)
        if direct_from_url:
            candidates.append(direct_from_url)

    derived_blob = _derive_elevenlabs_blob_name()
    if derived_blob:
        for container_candidate in [
            (blob_service.container_name or "").strip() or None,
            (container_from_url or "").strip() or None,
        ]:
            if not container_candidate:
                continue
            derived_url = blob_service.generate_sas_for_blob(container_candidate, derived_blob)
            if derived_url:
                candidates.append(derived_url)

    call_sid_value = str(call.call_sid or "").strip()
    if call_sid_value and blob_service.client:
        prefixes = _candidate_date_prefixes()
        container_candidates = list(
            dict.fromkeys(
                [
                    (blob_service.container_name or "").strip(),
                    (container_from_url or "").strip(),
                ]
            )
        )
        for container_candidate in [c for c in container_candidates if c]:
            found_blob = await asyncio.to_thread(
                blob_service.find_latest_blob_name,
                prefixes,
                call_sid_value,
                container_candidate,
            )
            if found_blob:
                searched_url = blob_service.generate_sas_for_blob(container_candidate, found_blob)
                if searched_url:
                    candidates.append(searched_url)

    resolved_url: Optional[str] = None
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for candidate in candidates:
            cleaned = str(candidate).strip().strip("`").strip().replace("`", "")
            try:
                resp = await client.get(cleaned, headers={"Range": "bytes=0-0"})
            except Exception:
                continue
            if 200 <= resp.status_code < 300:
                resolved_url = cleaned
                break

    if not resolved_url:
        raise HTTPException(status_code=404, detail="Recording not found in storage")

    async def generate():
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("GET", resolved_url) as resp:
                    if resp.status_code != 200:
                        yield b"Error fetching audio from storage"
                        return
                    async for chunk in resp.aiter_bytes():
                        yield chunk
            except Exception as e:
                import logging
                logging.error(f"Streaming error: {str(e)}")

    return StreamingResponse(generate(), media_type="audio/mpeg")


@router.get("/{call_id}/transcript", response_model=CallTranscript)
async def get_call_transcript(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CallTranscript:
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )
    if not call.transcript_text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not available for this call",
        )
    messages = [
        TranscriptMessage(
            role="assistant",
            content=call.transcript_text,
            timestamp=datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
        )
    ]
    return CallTranscript(
        call_id=call.id,
        call_sid=call.call_sid,
        messages=messages,
        summary=call.transcript_summary,
    )


@router.post("/{call_id}/outcome", response_model=CallResponse)
async def set_call_outcome(
    call_id: int,
    request: CallOutcomeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Call:
    """Set call outcome classification."""
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )
    
    call.outcome = request.outcome.value
    call.outcome_notes = request.notes
    
    await db.flush()
    await db.refresh(call)
    
    return call


@router.post("/{call_id}/notes", response_model=CallResponse)
async def add_call_notes(
    call_id: int,
    request: CallNotesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Call:
    """Add notes to a call."""
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )
    
    # Append to existing notes
    if call.outcome_notes:
        call.outcome_notes = f"{call.outcome_notes}\n\n{request.notes}"
    else:
        call.outcome_notes = request.notes
    
    await db.flush()
    await db.refresh(call)
    
    return call


class ToolCreateLeadRequest(BaseModel):
    phone: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    source: LeadSource = LeadSource.OUTBOUND_CALL
    notes: Optional[str] = None


class ToolCreateLeadResponse(BaseModel):
    success: bool
    lead_id: Optional[int] = None
    existing: bool = False
    message: str


class ToolGetExistingLeadRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class ToolGetExistingLeadResponse(BaseModel):
    found: bool
    lead_id: Optional[int] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    quality: Optional[str] = None
    status: Optional[str] = None


class ToolBookAppointmentRequest(BaseModel):
    lead_id: int
    scheduled_for: datetime
    address: str
    contact_number: Optional[str] = None
    notes: Optional[str] = None
    call_id: Optional[int] = None
    external_call_id: Optional[str] = None


class ToolBookAppointmentResponse(BaseModel):
    success: bool
    lead_id: Optional[int] = None
    enquiry_id: Optional[int] = None
    message: str


class ToolStartCallRequest(BaseModel):
    external_call_id: str
    direction: CallDirection
    from_number: str
    to_number: str


class ToolStartCallResponse(BaseModel):
    success: bool
    call_id: Optional[int] = None
    message: str


class ToolStoreRecordingRequest(BaseModel):
    external_call_id: str
    recording_url: str
    duration_seconds: Optional[int] = None


class ToolStoreRecordingResponse(BaseModel):
    success: bool
    recording_url: str
    message: str


class ToolGetSystemDateResponse(BaseModel):
    success: bool
    current_system_date: str


class ToolSaveSummaryRequest(BaseModel):
    external_call_id: str
    summary: str


class ToolSaveSummaryResponse(BaseModel):
    success: bool
    message: str


@router.post("/tools/create_lead", response_model=ToolCreateLeadResponse)
async def tool_create_lead(
    payload: ToolCreateLeadRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_elevenlabs_api_key),
) -> ToolCreateLeadResponse:
    result = await db.execute(select(Lead).where(Lead.phone == payload.phone))
    lead = result.scalar_one_or_none()
    
    if lead:
        updated = False
        if payload.name and not lead.name:
            lead.name = payload.name
            updated = True
        if payload.email and not lead.email:
            lead.email = payload.email
            updated = True
        if payload.notes:
            if lead.notes:
                lead.notes = f"{lead.notes}\n\n{payload.notes}"
            else:
                lead.notes = payload.notes
            updated = True
        if updated:
            await db.flush()
        return ToolCreateLeadResponse(
            success=True,
            lead_id=lead.id,
            existing=True,
            message="Lead already existed and was updated.",
        )
    
    lead = Lead(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        source=payload.source.value,
        notes=payload.notes,
        status=LeadStatus.NEW.value,
        quality=LeadQuality.COLD.value,
    )
    db.add(lead)
    await db.flush()
    await db.refresh(lead)
    
    return ToolCreateLeadResponse(
        success=True,
        lead_id=lead.id,
        existing=False,
        message="Lead created successfully.",
    )


@router.post("/tools/get_existing_lead", response_model=ToolGetExistingLeadResponse)
async def tool_get_existing_lead(
    payload: ToolGetExistingLeadRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_elevenlabs_api_key),
) -> ToolGetExistingLeadResponse:
    if not payload.phone and not payload.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either phone or email must be provided.",
        )
    
    query = select(Lead)
    if payload.phone:
        query = query.where(Lead.phone == payload.phone)
    elif payload.email:
        query = query.where(Lead.email == payload.email)
    
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    
    if not lead:
        return ToolGetExistingLeadResponse(found=False)
    
    return ToolGetExistingLeadResponse(
        found=True,
        lead_id=lead.id,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        quality=lead.quality,
        status=lead.status,
    )


@router.post("/tools/start_call", response_model=ToolStartCallResponse)
async def tool_start_call(
    payload: ToolStartCallRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_elevenlabs_api_key),
) -> ToolStartCallResponse:
    logger = get_logger("api.calls")
    logger.info(
        "tool_start_call_request",
        external_call_id=payload.external_call_id,
        direction=payload.direction.value,
        from_number=payload.from_number,
        to_number=payload.to_number,
    )
    result = await db.execute(select(Call).where(Call.call_sid == payload.external_call_id))
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(
            "tool_start_call_existing",
            call_id=existing.id,
            call_sid=existing.call_sid,
        )
        return ToolStartCallResponse(
            success=True,
            call_id=existing.id,
            message="Call already exists.",
        )

    call = Call(
        call_sid=payload.external_call_id,
        direction=payload.direction.value,
        from_number=payload.from_number,
        to_number=payload.to_number,
        status=CallStatus.INITIATED.value,
        started_at=datetime.now(ZoneInfo("Asia/Kolkata")),
        handled_by_ai=True,
    )
    db.add(call)
    await db.flush()
    await db.refresh(call)
    await db.commit()
    logger.info(
        "tool_start_call_created",
        call_id=call.id,
        call_sid=call.call_sid,
    )
    return ToolStartCallResponse(
        success=True,
        call_id=call.id,
        message="Call initialized.",
    )


@router.post("/tools/book_appointment", response_model=ToolBookAppointmentResponse)
async def tool_book_appointment(
    payload: ToolBookAppointmentRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_elevenlabs_api_key),
) -> ToolBookAppointmentResponse:
    logger = get_logger("api.calls")
    logger.info(
        "tool_book_appointment_request",
        lead_id=payload.lead_id,
        call_id=payload.call_id,
        external_call_id=payload.external_call_id,
        scheduled_for=payload.scheduled_for.isoformat(),
        address=payload.address,
        contact_number=payload.contact_number,
    )
    try:
        result = await db.execute(select(Lead).where(Lead.id == payload.lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            logger.warning(
                "tool_book_appointment_lead_not_found",
                lead_id=payload.lead_id,
            )
            return ToolBookAppointmentResponse(
                success=False,
                lead_id=None,
                enquiry_id=None,
                message="Lead not found for appointment booking.",
            )
        contact_number = payload.contact_number or lead.phone

        call = None
        if payload.external_call_id:
            result_call = await db.execute(
                select(Call).where(Call.call_sid == payload.external_call_id)
            )
            call = result_call.scalar_one_or_none()
        if call is None and payload.call_id is not None:
            result_call = await db.execute(select(Call).where(Call.id == payload.call_id))
            call = result_call.scalar_one_or_none()
        if call is None:
            logger.warning(
                "tool_book_appointment_call_not_found",
                lead_id=payload.lead_id,
                call_id=payload.call_id,
                external_call_id=payload.external_call_id,
            )
            if payload.external_call_id:
                call = Call(
                    call_sid=payload.external_call_id,
                    direction=CallDirection.OUTBOUND.value,
                    from_number=settings.twilio_phone_number,
                    to_number=lead.phone or settings.twilio_phone_number,
                    status=CallStatus.IN_PROGRESS.value,
                    started_at=datetime.now(ZoneInfo("Asia/Kolkata")),
                    handled_by_ai=True,
                )
                db.add(call)
                await db.flush()
            else:
                return ToolBookAppointmentResponse(
                    success=False,
                    lead_id=lead.id,
                    enquiry_id=None,
                    message="Call not found for appointment booking.",
                )
        result_appt = await db.execute(
            select(Appointment).where(
                Appointment.call_id == call.id,
                Appointment.lead_id == lead.id,
            )
        )
        appointment = result_appt.scalar_one_or_none()
        if appointment is None:
            appointment = Appointment(
                call_id=call.id,
                lead_id=lead.id,
                scheduled_for=payload.scheduled_for,
                address=payload.address,
                contact_number=contact_number,
                notes=payload.notes,
                status=AppointmentStatus.SCHEDULED.value,
            )
            db.add(appointment)
        else:
            appointment.scheduled_for = payload.scheduled_for
            appointment.address = payload.address
            appointment.contact_number = contact_number
            appointment.notes = payload.notes
            if appointment.status in {
                AppointmentStatus.CANCELLED.value,
                AppointmentStatus.NO_SHOW.value,
            }:
                appointment.status = AppointmentStatus.SCHEDULED.value
        query_text = (
            f"Site visit scheduled for {payload.scheduled_for.isoformat()} at {payload.address}."
        )
        if payload.notes:
            query_text = f"{query_text} Notes: {payload.notes}"
        result_enquiry = await db.execute(
            select(Enquiry).where(
                Enquiry.call_id == call.id,
                Enquiry.lead_id == lead.id,
                Enquiry.enquiry_type == EnquiryType.SITE_VISIT.value,
            )
        )
        enquiry = result_enquiry.scalar_one_or_none()
        if enquiry is None:
            enquiry = Enquiry(
                call_id=call.id,
                lead_id=lead.id,
                enquiry_type=EnquiryType.SITE_VISIT.value,
                query_text=query_text,
                response_successful=True,
            )
            db.add(enquiry)
        else:
            enquiry.query_text = query_text
            enquiry.response_successful = True
        lead.status = LeadStatus.QUALIFIED.value
        lead.quality = LeadQuality.WARM.value
        await db.flush()
        await db.refresh(enquiry)
        await db.refresh(appointment)
        await db.commit()
        logger.info(
            "tool_book_appointment_success",
            lead_id=lead.id,
            call_id=call.id,
            appointment_id=appointment.id,
            enquiry_id=enquiry.id,
        )

        notification_service = NotificationService(db)
        result_users = await db.execute(
            select(User).where(
                User.role.in_([UserRole.ADMIN.value, UserRole.MANAGER.value])
            )
        )
        admins = result_users.scalars().all()
        scheduled_for_ist = appointment.scheduled_for.astimezone(ZoneInfo("Asia/Kolkata")).strftime(
            "%Y-%m-%d %H:%M"
        )
        for admin in admins:
            await notification_service.create_notification(
                user_id=admin.id,
                message=(
                    f"Appointment booked for lead {lead.phone} on "
                    f"{scheduled_for_ist}"
                ),
                notification_type=NotificationType.APPOINTMENT_BOOKED,
                related_lead_id=lead.id,
            )
        return ToolBookAppointmentResponse(
            success=True,
            lead_id=lead.id,
            enquiry_id=enquiry.id,
            message="Appointment booked and enquiry recorded.",
        )
    except Exception as e:
        await db.rollback()
        logger.error("tool_book_appointment_failed", error=str(e))
        return ToolBookAppointmentResponse(
            success=False,
            lead_id=payload.lead_id,
            enquiry_id=None,
            message="Failed to book appointment.",
        )


@router.post("/tools/store_recording", response_model=ToolStoreRecordingResponse)
async def tool_store_recording(
    payload: ToolStoreRecordingRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_elevenlabs_api_key),
) -> ToolStoreRecordingResponse:
    result = await db.execute(select(Call).where(Call.call_sid == payload.external_call_id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found for recording storage.",
        )

    blob_service = BlobService()
    if not blob_service.client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Azure Blob Storage is not configured.",
        )

    async with httpx.AsyncClient() as client:
        resp = await client.get(payload.recording_url, timeout=60.0)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to download recording from source URL.",
        )

    date_prefix = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    file_name = f"{date_prefix}/{call.call_sid}.mp3"
    azure_url = await blob_service.upload_file(
        file_data=resp.content,
        file_name=file_name,
        content_type="audio/mpeg",
    )
    if not azure_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload recording to Azure Blob Storage.",
        )

    call.recording_url = azure_url
    if payload.duration_seconds is not None:
        call.recording_duration = payload.duration_seconds

    await db.flush()
    await db.refresh(call)
    await db.commit()

    return ToolStoreRecordingResponse(
        success=True,
        recording_url=call.recording_url,
        message="Recording stored in Azure and call updated.",
    )


@router.post("/tools/get_system_date", response_model=ToolGetSystemDateResponse)
async def tool_get_system_date(
    api_key: str = Depends(verify_elevenlabs_api_key),
) -> ToolGetSystemDateResponse:
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    system_date = now.date().isoformat()

    return ToolGetSystemDateResponse(
        success=True,
        current_system_date=system_date,
    )


@router.post("/tools/save_summary", response_model=ToolSaveSummaryResponse)
async def tool_save_summary(
    payload: ToolSaveSummaryRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_elevenlabs_api_key),
) -> ToolSaveSummaryResponse:
    logger = get_logger("api.calls")
    try:
        if not payload.summary or not payload.summary.strip():
            return ToolSaveSummaryResponse(
                success=False,
                message="Empty summary payload.",
            )
        result = await db.execute(select(Call).where(Call.call_sid == payload.external_call_id))
        call = result.scalar_one_or_none()
        if not call:
            logger.warning(
                "tool_save_summary_call_not_found",
                external_call_id=payload.external_call_id,
            )
            return ToolSaveSummaryResponse(
                success=False,
                message="Call not found for summary storage.",
            )
        call.transcript_summary = payload.summary
        await db.flush()
        await db.refresh(call)
        await db.commit()
        return ToolSaveSummaryResponse(
            success=True,
            message="Call summary saved.",
        )
    except Exception as e:
        await db.rollback()
        logger.error(
            "tool_save_summary_failed",
            external_call_id=payload.external_call_id,
            error=str(e),
        )
        return ToolSaveSummaryResponse(
            success=False,
            message="Failed to save summary.",
        )


class HumanDialRequest(BaseModel):
    to_number: str
    lead_id: Optional[int] = None


class ElevenLabsUserDialRequest(BaseModel):
    to_number: str
    voice_id: Optional[str] = None


@router.post("/dial/elevenlabs", response_model=CallResponse)
async def dial_elevenlabs_number(
    request: ElevenLabsUserDialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Call:
    if not current_user.is_agent_role and not current_user.is_manager and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agents and managers can initiate ElevenLabs outbound calls.",
        )
    if TwilioClient is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio is not available on this server.",
        )
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio credentials are not configured.",
        )

    try:
        formatted_number = clean_indian_number(request.to_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    voice_id = request.voice_id or settings.elevenlabs_voice_id
    if not voice_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ElevenLabs voice ID is not configured.",
        )
    if not settings.elevenlabs_realtime_ws_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ElevenLabs realtime WebSocket URL is not configured.",
        )

    logger = get_logger("api.calls")
    try:
        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

        twiml_url = f"{settings.base_url}/twilio/elevenlabs-outbound?voice_id={voice_id}"

        call_kwargs = {
            "to": formatted_number,
            "from_": settings.twilio_phone_number,
            "url": twiml_url,
            "method": "POST",
            "status_callback": f"{settings.base_url}/twilio/call-status",
            "status_callback_event": ["initiated", "ringing", "answered", "completed"],
            "status_callback_method": "POST",
            "record": True,
            "recording_status_callback": f"{settings.base_url}/twilio/recording-status",
            "recording_status_callback_method": "POST",
        }

        call = client.calls.create(**call_kwargs)

        db_call = Call(
            call_sid=call.sid,
            from_number=settings.twilio_phone_number,
            to_number=formatted_number,
            direction=CallDirection.OUTBOUND.value,
            status=CallStatus.INITIATED.value,
            started_at=datetime.now(ZoneInfo("Asia/Kolkata")),
            handled_by_ai=True,
        )

        db.add(db_call)
        await db.commit()
        await db.refresh(db_call)

        logger.info(
            "elevenlabs_outbound_call_initiated_ui",
            call_id=db_call.id,
            call_sid=db_call.call_sid,
            from_number=db_call.from_number,
            to_number=db_call.to_number,
            voice_id=voice_id,
        )

        return db_call
    except TwilioRestException as e:
        logger.error("elevenlabs_twilio_error_ui", code=e.code, msg=e.msg, status=e.status)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Twilio Error ({e.code}): {e.msg}",
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("elevenlabs_outbound_call_failed_ui", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate ElevenLabs call: {str(e)}",
        )


@router.post("/dial/human", response_model=CallResponse)
async def human_dial_number(
    request: HumanDialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Call:
    if not current_user.is_agent_role and not current_user.is_manager and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agents and managers can initiate human outbound calls.",
        )
    try:
        if TwilioClient is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Twilio is not available on this server.",
            )
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Twilio credentials are not configured.",
            )
        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        
        call_kwargs = {
            "to": request.to_number,
            "from_": settings.twilio_phone_number,
            "status_callback": f"{settings.base_url}/twilio/call-status",
            "status_callback_event": ["initiated", "ringing", "answered", "completed"],
            "status_callback_method": "POST",
            "record": True,
            "recording_status_callback": f"{settings.base_url}/twilio/recording-status",
            "recording_status_callback_method": "POST",
        }
        
        if settings.twilio_application_sid:
            call_kwargs["application_sid"] = settings.twilio_application_sid
        else:
            webhook_url = f"{settings.base_url}/twilio/outbound-webhook"
            if request.lead_id:
                webhook_url += f"?lead_id={request.lead_id}"
            call_kwargs["url"] = webhook_url
            call_kwargs["method"] = "POST"
        
        call = client.calls.create(**call_kwargs)
        
        db_call = Call(
            call_sid=call.sid,
            from_number=settings.twilio_phone_number,
            to_number=request.to_number,
            direction=CallDirection.OUTBOUND.value,
            status=CallStatus.INITIATED.value,
            started_at=datetime.now(ZoneInfo("Asia/Kolkata")),
            handled_by_ai=False,
            escalated_to_human=True,
            escalated_to_agent_id=current_user.id,
            lead_id=request.lead_id,
        )
        
        db.add(db_call)
        await db.commit()
        await db.refresh(db_call)
        
        return db_call
    except TwilioRestException as e:
        logger = get_logger("api.calls")
        logger.error("twilio_human_error", code=e.code, msg=e.msg, status=e.status)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Twilio Error ({e.code}): {e.msg}",
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate human call: {str(e)}",
        )


@router.post("/tools/elevenlabs_dial", response_model=CallResponse)
async def elevenlabs_dial_number(
    request: ElevenLabsDialRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_elevenlabs_api_key),
) -> Call:
    logger = get_logger("api.calls")
    try:
        if TwilioClient is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Twilio is not available on this server.",
            )
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Twilio credentials are not configured.",
            )
        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

        if not settings.elevenlabs_realtime_ws_url:
            logger.error("elevenlabs_realtime_ws_url_not_configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="ElevenLabs realtime WebSocket URL is not configured.",
            )

        twiml_url = (
            f"{settings.base_url}/twilio/elevenlabs-outbound"
            f"?voice_id={request.voice_id}"
        )

        call_kwargs = {
            "to": request.recipient_number,
            "from_": request.caller_id,
            "url": twiml_url,
            "method": "POST",
            "status_callback": f"{settings.base_url}/twilio/call-status",
            "status_callback_event": ["initiated", "ringing", "answered", "completed"],
            "status_callback_method": "POST",
            "record": True,
            "recording_status_callback": f"{settings.base_url}/twilio/recording-status",
            "recording_status_callback_method": "POST",
        }

        call = client.calls.create(**call_kwargs)

        db_call = Call(
            call_sid=call.sid,
            from_number=request.caller_id,
            to_number=request.recipient_number,
            direction=CallDirection.OUTBOUND.value,
            status=CallStatus.INITIATED.value,
            started_at=datetime.now(ZoneInfo("Asia/Kolkata")),
            handled_by_ai=True,
        )

        db.add(db_call)
        await db.commit()
        await db.refresh(db_call)

        logger.info(
            "elevenlabs_outbound_call_initiated",
            call_id=db_call.id,
            call_sid=db_call.call_sid,
            from_number=db_call.from_number,
            to_number=db_call.to_number,
            voice_id=request.voice_id,
        )

        return db_call

    except TwilioRestException as e:
        logger.error("elevenlabs_twilio_error", code=e.code, msg=e.msg, status=e.status)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Twilio Error ({e.code}): {e.msg}",
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("elevenlabs_outbound_call_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate ElevenLabs call: {str(e)}",
        )
