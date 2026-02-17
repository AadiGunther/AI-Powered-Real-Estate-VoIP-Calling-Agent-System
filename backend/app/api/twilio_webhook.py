"""Twilio webhook endpoints for VoIP call handling."""

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request, Response, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.twiml.voice_response import VoiceResponse, Connect

from app.config import settings
from app.database import get_db
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
    response = VoiceResponse()
    response.say("This calling flow is currently unavailable.")
    response.hangup()
    return Response(content=str(response), media_type="application/xml")

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
                started_at=datetime.now(ZoneInfo("Asia/Kolkata")),
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
                call.started_at = datetime.now(ZoneInfo("Asia/Kolkata"))
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
    response = VoiceResponse()
    response.say("This calling flow is currently unavailable.")
    response.hangup()
    return Response(content=str(response), media_type="application/xml")

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


@router.post("/elevenlabs-outbound")
async def handle_elevenlabs_outbound_call(
    CallSid: str = Form(..., alias="CallSid"),
    From: str = Form(..., alias="From"),
    To: str = Form(..., alias="To"),
    voice_id: str = Query(...),
) -> Response:
    """
    TwiML for outbound calls that stream audio directly to ElevenLabs realtime WebSocket.
    """
    try:
        if not settings.elevenlabs_realtime_ws_url:
            logger.error("elevenlabs_realtime_ws_url_not_configured")
            raise HTTPException(
                status_code=500,
                detail="ElevenLabs realtime WebSocket URL is not configured.",
            )

        logger.info(
            "elevenlabs_outbound_twiml_request",
            call_sid=CallSid,
            from_number=From,
            to_number=To,
            voice_id=voice_id,
        )

        response = VoiceResponse()

        connect = Connect()
        stream = connect.stream(url=settings.elevenlabs_realtime_ws_url)
        stream.parameter(name="call_sid", value=CallSid)
        stream.parameter(name="from_number", value=From)
        stream.parameter(name="to_number", value=To)
        stream.parameter(name="voice_id", value=voice_id)

        response.append(connect)

        return Response(
            content=str(response),
            media_type="application/xml",
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("elevenlabs_outbound_twiml_failed", error=str(e), call_sid=CallSid)
        raise HTTPException(status_code=500, detail=str(e))
        
@router.post("/call-status")
async def handle_call_status_recording(
    CallSid: str = Form(..., alias="CallSid"),
    CallStatusParam: str = Form(..., alias="CallStatus"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Handle Twilio status callback and start recording when call is in-progress or answered.
    """
    try:
        logger.info(
            "call_status_event",
            call_sid=CallSid,
            status=CallStatusParam,
        )

        status_lower = CallStatusParam.lower()
        if status_lower not in ("in-progress", "answered"):
            return {"status": "ignored"}

        result = await db.execute(select(Call).where(Call.call_sid == CallSid))
        call = result.scalar_one_or_none()

        if call and call.recording_sid:
            logger.info(
                "recording_already_started",
                call_sid=CallSid,
                recording_sid=call.recording_sid,
            )
            return {"status": "already_recording"}

        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

        def create_recording():
            return client.calls(CallSid).recordings.create(
                recording_channels="dual",
                recording_status_callback=f"{settings.base_url}/twilio/recording-status",
            )

        recording = await asyncio.to_thread(create_recording)

        if call:
            call.recording_sid = recording.sid
            await db.flush()

        logger.info(
            "recording_started",
            call_sid=CallSid,
            recording_sid=recording.sid,
        )
        return {"status": "recording_started"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("call_status_recording_failed", error=str(e), call_sid=CallSid)
        return {"status": "error", "message": str(e)}


@router.post("/recording-status")
async def handle_recording_status_event(
    CallSid: str = Form(..., alias="CallSid"),
    RecordingSid: Optional[str] = Form(None, alias="RecordingSid"),
    RecordingUrl: Optional[str] = Form(None, alias="RecordingUrl"),
    RecordingDuration: Optional[str] = Form(None, alias="RecordingDuration"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Handle Twilio recording status callback for logging and basic persistence.
    """
    try:
        logger.info(
            "recording_status_event",
            call_sid=CallSid,
            recording_sid=RecordingSid,
            recording_url=RecordingUrl,
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
                        date_prefix = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
                        file_name = f"{date_prefix}/{CallSid}_{RecordingSid or 'no_sid'}.mp3"
                        azure_url = await blob_service.upload_file(
                            file_data=resp.content,
                            file_name=file_name,
                            content_type="audio/mpeg",
                        )
                    else:
                        logger.error("recording_download_failed", status=resp.status_code)
            except Exception as e:
                logger.error("recording_processing_failed", error=str(e), call_sid=CallSid)

            call.recording_url = azure_url if azure_url else RecordingUrl
            if RecordingSid:
                call.recording_sid = RecordingSid
            if RecordingDuration:
                try:
                    call.recording_duration = int(RecordingDuration)
                except ValueError:
                    logger.error(
                        "recording_duration_parse_failed",
                        raw=RecordingDuration,
                        call_sid=CallSid,
                    )
            await db.flush()
            await db.commit()

        return {"status": "ok"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("recording_status_failed", error=str(e), call_sid=CallSid)
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
