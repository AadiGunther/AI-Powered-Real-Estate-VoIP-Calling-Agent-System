"""Twilio webhook endpoints for VoIP call handling."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Response, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.twiml.voice_response import VoiceResponse, Connect

from app.config import settings
from app.database import get_db, get_mongodb
from app.models.call import Call, CallDirection, CallStatus
from app.models.lead import Lead, LeadSource, LeadQuality, LeadStatus
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger("twilio.webhook")


@router.api_route("/webhook", methods=["GET", "POST"])
async def handle_incoming_call(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Handle incoming Twilio call webhook.
    Returns TwiML with <Stream> to connect to our media stream WebSocket.
    """
    try:
        # Get data from either Form or Query
        if request.method == "POST":
            data = await request.form()
        else:
            data = request.query_params

        CallSid = data.get("CallSid")
        From = data.get("From")
        To = data.get("To")
        Direction = data.get("Direction", "inbound")
        
        logger.info(
            "incoming_call",
            call_sid=CallSid,
            from_number=From,
            to_number=To,
            direction=Direction,
        )
        
        # Create call record in database
        call = Call(
            call_sid=CallSid,
            from_number=From,
            to_number=To,
            direction=CallDirection.INBOUND.value if Direction == "inbound" else CallDirection.OUTBOUND.value,
            status=CallStatus.RINGING.value,
            started_at=datetime.now(timezone.utc),
            handled_by_ai=True,
        )
        
        db.add(call)
        await db.flush()
        
        # Check if lead exists, create if not
        result = await db.execute(select(Lead).where(Lead.phone == From))
        lead = result.scalar_one_or_none()
        
        if not lead:
            lead = Lead(
                phone=From,
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.COLD.value,
                status=LeadStatus.NEW.value,
            )
            db.add(lead)
            await db.flush()
            call.lead_created = True
        
        call.lead_id = lead.id
        await db.flush()
        
        # Initialize transcript in MongoDB
        mongodb = get_mongodb()
        await mongodb.transcripts.insert_one({
            "call_sid": CallSid,
            "call_id": call.id,
            "lead_id": lead.id,
            "messages": [],
            "created_at": datetime.now(timezone.utc),
        })
        
        # Generate TwiML response with media stream
        response = VoiceResponse()

        connect = Connect()
        stream = connect.stream(url=settings.websocket_url)
        stream.parameter(name="call_sid", value=CallSid)
        stream.parameter(name="from_number", value=From)
        stream.parameter(name="lead_id", value=str(lead.id))

        response.append(connect)

        # 🔑 KEEP THE CALL ALIVE
        response.pause(length=3600)

        return Response(
            content=str(response),
            media_type="application/xml",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("incoming_call_failed", error=str(e), call_sid=CallSid)
        raise HTTPException(status_code=500, detail=str(e))

@router.api_route("/outbound-webhook", methods=["GET", "POST"])
async def handle_outbound_call(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Handle outbound Twilio call TwiML logic.
    Returns TwiML with <Stream> to connect to our media stream WebSocket.
    """
    try:
        # Get data from either Form or Query
        if request.method == "POST":
            data = await request.form()
        else:
            data = request.query_params

        CallSid = data.get("CallSid")
        To = data.get("To")
        From = data.get("From")
        lead_id = data.get("lead_id")

        logger.info(
            "outbound_call_connected",
            call_sid=CallSid,
            to_number=To,
            from_number=From,
        )
        
        # If lead_id is missing (from TwiML app), try to fetch from DB
        if not lead_id:
            result = await db.execute(select(Call).where(Call.call_sid == CallSid))
            call = result.scalar_one_or_none()
            if call and call.lead_id:
                lead_id = str(call.lead_id)

        response = VoiceResponse()

        connect = Connect()
        stream = connect.stream(url=settings.websocket_url)
        stream.parameter(name="call_sid", value=CallSid)
        stream.parameter(name="direction", value="outbound")
        stream.parameter(name="to_number", value=To)

        response.append(connect)

        # 🔑 KEEP THE CALL ALIVE
        response.pause(length=3600)

        return Response(
            content=str(response),
            media_type="application/xml",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("outbound_webhook_failed", error=str(e), call_sid=CallSid)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/status")
async def handle_call_status(
    CallSid: str = Form(..., alias="CallSid"),
    CallStatusParam: str = Form(..., alias="CallStatus"),
    CallDuration: Optional[str] = Form(None, alias="CallDuration"),
    RecordingUrl: Optional[str] = Form(None, alias="RecordingUrl"),
    RecordingSid: Optional[str] = Form(None, alias="RecordingSid"),
    RecordingDuration: Optional[str] = Form(None, alias="RecordingDuration"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle Twilio call status webhook."""
    try:
        logger.info(
            "call_status_update",
            call_sid=CallSid,
            status=CallStatusParam,
            duration=CallDuration,
        )
        
        # Map Twilio status to our status
        status_map = {
            "initiated": CallStatus.INITIATED,
            "ringing": CallStatus.RINGING,
            "in-progress": CallStatus.IN_PROGRESS,
            "completed": CallStatus.COMPLETED,
            "failed": CallStatus.FAILED,
            "busy": CallStatus.BUSY,
            "no-answer": CallStatus.NO_ANSWER,
            "canceled": CallStatus.CANCELLED,
        }
        
        # Update call record
        result = await db.execute(select(Call).where(Call.call_sid == CallSid))
        call = result.scalar_one_or_none()
        
        if call:
            call.status = status_map.get(CallStatusParam.lower(), CallStatus.COMPLETED).value
            
            if CallDuration:
                call.duration_seconds = int(CallDuration)
                call.ended_at = datetime.now(timezone.utc)
            
            if RecordingUrl:
                call.recording_url = RecordingUrl
                call.recording_sid = RecordingSid
                if RecordingDuration:
                    call.recording_duration = int(RecordingDuration)
            
            await db.flush()
        
        return {"status": "processed"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("status_webhook_failed", error=str(e), call_sid=CallSid)
        return {"status": "error", "message": str(e)}



@router.post("/recording")
async def handle_recording_status(
    CallSid: str = Form(..., alias="CallSid"),
    RecordingUrl: str = Form(..., alias="RecordingUrl"),
    RecordingSid: str = Form(..., alias="RecordingSid"),
    RecordingDuration: str = Form(..., alias="RecordingDuration"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle Twilio recording status webhook."""
    try:
        logger.info(
            "recording_complete",
            call_sid=CallSid,
            recording_sid=RecordingSid,
            duration=RecordingDuration,
        )
        
        result = await db.execute(select(Call).where(Call.call_sid == CallSid))
        call = result.scalar_one_or_none()
        
        if call:
            call.recording_url = RecordingUrl
            call.recording_sid = RecordingSid
            call.recording_duration = int(RecordingDuration)
            await db.flush()
        
        return {"status": "processed"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("recording_webhook_failed", error=str(e), call_sid=CallSid)
        return {"status": "error", "message": str(e)}


@router.post("/fallback")
async def handle_fallback(
    CallSid: str = Form(..., alias="CallSid"),
    ErrorCode: Optional[str] = Form(None, alias="ErrorCode"),
    ErrorUrl: Optional[str] = Form(None, alias="ErrorUrl"),
) -> Response:
    """Handle Twilio fallback for failed webhooks."""
    try:
        logger.error(
            "webhook_fallback",
            call_sid=CallSid,
            error_code=ErrorCode,
            error_url=ErrorUrl,
        )
        
        # Return a simple TwiML response to handle the call gracefully
        response = VoiceResponse()
        response.say(
            "We're sorry, we're experiencing technical difficulties. "
            "Please try again later or contact us at our main office.",
            voice="Polly.Joanna"
        )
        response.hangup()
        
        return Response(
            content=str(response),
            media_type="application/xml",
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(content="Error in fallback", status_code=500)
