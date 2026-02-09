"""Calls API endpoints."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, get_mongodb
from app.models.user import User, UserRole
from app.models.call import Call, CallStatus, CallOutcome, CallDirection
from app.schemas.call import (
    CallResponse,
    CallListResponse,
    CallOutcomeUpdate,
    CallNotesUpdate,
    CallTranscript,
    TranscriptMessage,
    DialRequest,
)
from app.utils.security import get_current_user
from app.utils.logging import get_logger
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

router = APIRouter()


@router.post("/dial", response_model=CallResponse)
async def dial_number(
    request: DialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Call:
    """Initiate an outbound call."""
    try:
        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        
        # Use TwiML App SID if configured, otherwise fallback to direct URL
        call_kwargs = {
            "to": request.to_number,
            "from_": settings.twilio_phone_number,
            "status_callback": f"{settings.base_url}/twilio/status",
            "status_callback_event": ["initiated", "ringing", "answered", "completed"],
            "status_callback_method": "POST",
            "record": True,
            "recording_status_callback": f"{settings.base_url}/twilio/recording",
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
            started_at=datetime.now(timezone.utc),
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
                detail="Twilio Trial Account Restriction: The destination number is not verified. Please verify the number in your Twilio console or upgrade your account."
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
    query = select(Call)
    
    # Role-based filtering
    if current_user.role == UserRole.AGENT.value:
        query = query.where(Call.escalated_to_agent_id == current_user.id)
    
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
    """Get call recording URL."""
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
    
    return {
        "call_id": call.id,
        "call_sid": call.call_sid,
        "recording_url": call.recording_url,
        "duration": call.recording_duration,
    }


@router.get("/{call_id}/transcript", response_model=CallTranscript)
async def get_call_transcript(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CallTranscript:
    """Get call transcript from MongoDB."""
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )
    
    if not call.transcript_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not available for this call",
        )
    
    # Fetch transcript from MongoDB Reports collection (merged)
    mongodb = get_mongodb()
    report_doc = await mongodb.reports.find_one({"call_sid": call.call_sid})
    
    if not report_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript/Report document not found",
        )
    
    messages = [
        TranscriptMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg.get("timestamp", datetime.now().isoformat()),
        )
        for msg in report_doc.get("messages", [])
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
