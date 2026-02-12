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
from app.services.blob_service import BlobService
import httpx
import asyncio
from twilio.rest import Client as TwilioClient

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
        
        result = await db.execute(select(Call).where(Call.call_sid == CallSid))
        call = result.scalar_one_or_none()
        
        if call is None:
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
        else:
            call.from_number = From
            call.to_number = To
            call.direction = CallDirection.INBOUND.value if Direction == "inbound" else CallDirection.OUTBOUND.value
            call.status = CallStatus.RINGING.value
            if call.started_at is None:
                call.started_at = datetime.now(timezone.utc)
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
        
        # Start recording via API
        async def start_twilio_recording():
            try:
                client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
                await asyncio.to_thread(
                    lambda: client.calls(CallSid).update(
                        record=True,
                        recording_status_callback=f"{settings.base_url}/twilio/recording",
                        recording_status_callback_method="POST"
                    )
                )
            except Exception as e:
                logger.error("start_recording_failed", error=str(e), call_sid=CallSid)
        
        asyncio.create_task(start_twilio_recording())

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
            incoming = CallStatusParam.lower()
            new_status_enum = status_map.get(incoming, CallStatus.COMPLETED)
            new_status = new_status_enum.value
            
            current_status = call.status
            terminal_statuses = {
                CallStatus.COMPLETED.value,
                CallStatus.FAILED.value,
                CallStatus.NO_ANSWER.value,
                CallStatus.BUSY.value,
                CallStatus.CANCELLED.value,
            }
            
            # Do not downgrade from a terminal status back to in-progress/ringing/etc.
            if current_status in terminal_statuses and new_status not in terminal_statuses:
                logger.info(
                    "call_status_downgrade_ignored",
                    call_sid=CallSid,
                    current_status=current_status,
                    incoming_status=new_status,
                )
            else:
                call.status = new_status
            
            # Set timing fields
            if new_status == CallStatus.IN_PROGRESS.value and not call.started_at:
                call.started_at = datetime.now(timezone.utc)
            
            if new_status == CallStatus.RINGING.value and not call.created_at:
                # Should be set on creation, but just in case
                pass
                
            # If Twilio sends duration, trust it for end timing
            if CallDuration:
                try:
                    call.duration_seconds = int(CallDuration)
                except ValueError:
                    logger.error("call_duration_parse_failed", raw=CallDuration, call_sid=CallSid)
                call.ended_at = datetime.now(timezone.utc)
            # If status is terminal but no duration provided, ensure we still set ended_at/duration
            elif new_status in terminal_statuses:
                if not call.ended_at:
                    call.ended_at = datetime.now(timezone.utc)
                if call.started_at and not call.duration_seconds:
                    call.duration_seconds = int(
                        (call.ended_at - call.started_at).total_seconds()
                    )
            
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
    RecordingUrl: Optional[str] = Form(None, alias="RecordingUrl"),
    RecordingSid: Optional[str] = Form(None, alias="RecordingSid"),
    RecordingDuration: Optional[str] = Form(None, alias="RecordingDuration"),
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
        
        if call and RecordingUrl:
            azure_url = None
            try:
                async with httpx.AsyncClient() as client:
                    download_url = f"{RecordingUrl}.mp3"
                    resp = await client.get(
                        download_url,
                        timeout=60.0,
                        auth=(
                            settings.twilio_account_sid,
                            settings.twilio_auth_token,
                        ),
                    )
                    
                    if resp.status_code == 200:
                        blob_service = BlobService()
                        date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        file_name = f"{date_prefix}/{CallSid}_{RecordingSid or 'no_sid'}.mp3"
                        azure_url = await blob_service.upload_file(
                            file_data=resp.content,
                            file_name=file_name,
                            content_type="audio/mpeg"
                        )
                    else:
                        logger.error("recording_download_failed", status=resp.status_code)
            except Exception as e:
                logger.error("recording_processing_failed", error=str(e))

            call.recording_url = azure_url if azure_url else RecordingUrl
            call.recording_sid = RecordingSid
            if RecordingDuration:
                try:
                    call.recording_duration = int(RecordingDuration)
                except ValueError:
                    logger.error("recording_duration_parse_failed", raw=RecordingDuration)
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
            voice="Polly.Joanna-Neural"
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
