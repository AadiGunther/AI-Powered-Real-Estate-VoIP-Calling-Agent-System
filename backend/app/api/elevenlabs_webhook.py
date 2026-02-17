"""ElevenLabs webhook endpoints."""

import json
import hmac
import hashlib
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Optional, List, Dict
import base64
import re

import asyncio
import httpx
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker
from app.models.call import Call, CallStatus
from app.models.elevenlabs_event_log import ElevenLabsEventLog
from app.services.blob_service import BlobService
from app.utils.logging import get_logger


router = APIRouter()
logger = get_logger("elevenlabs_webhook")
_elevenlabs_rate_state: Dict[str, list[float]] = {}
_ELEVENLABS_RATE_WINDOW_SECONDS = 60.0
_ELEVENLABS_RATE_LIMIT = 120


def _safe_log(level: str, event: str, **kwargs: Any) -> None:
    try:
        log_func = getattr(logger, level, None)
        if log_func is not None:
            log_func(event, **kwargs)
    except Exception:
        pass


def _extract_call_sid(data: dict) -> Optional[str]:
    cid = data.get("conversation_initiation_client_data") or {}
    if isinstance(cid, dict):
        dyn = cid.get("dynamic_variables") or {}
        if isinstance(dyn, dict):
            for key in ("call_sid", "twilio_call_sid", "external_call_id", "call_id"):
                v = dyn.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()

    metadata = data.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("call_sid", "twilio_call_sid", "external_call_id", "call_id"):
            v = metadata.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

    for key in ("call_id", "call_sid", "external_call_id"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    conv_id = data.get("conversation_id")
    if isinstance(conv_id, str) and conv_id.strip():
        return conv_id.strip()

    return None


def _extract_transcript_and_summary(data: dict) -> tuple[str, str]:
    transcript_value = data.get("transcript") or ""
    summary_value = data.get("summary") or ""
    if not summary_value:
        analysis = data.get("analysis") or {}
        if isinstance(analysis, dict):
            summary_value = analysis.get("transcript_summary") or ""
    transcript_text = ""
    if isinstance(transcript_value, str):
        transcript_text = transcript_value
    elif isinstance(transcript_value, list):
        parts: List[str] = []
        for item in transcript_value:
            if not isinstance(item, dict):
                continue
            message = item.get("message")
            if isinstance(message, str) and message:
                parts.append(message)
        transcript_text = "\n".join(parts)
    summary_text = summary_value if isinstance(summary_value, str) else ""
    return transcript_text, summary_text


def _extract_username_from_transcript(transcript_text: str) -> Optional[str]:
    if not transcript_text:
        return None
    text = transcript_text.strip()
    if not text:
        return None
    patterns = [
        r"\bmy name is\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})",
        r"\bthis is\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})",
        r"\bhi[, ]+i['’]?m\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})",
        r"\bi am\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})",
    ]
    lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lower, re.IGNORECASE)
        if not match:
            continue
        start, end = match.span(1)
        candidate = text[start:end].strip()
        cleaned = re.sub(r"[^A-Za-z\s'-]", "", candidate).strip()
        if 1 < len(cleaned) <= 60:
            return cleaned
    return None


async def _ensure_call_initialized(
    db: AsyncSession,
    call_sid: str,
    data: dict,
    event_timestamp: int,
    context: str,
) -> Optional[Call]:
    result = await db.execute(select(Call).where(Call.call_sid == call_sid))
    call = result.scalar_one_or_none()
    if call:
        return call
    direction_raw = data.get("direction") or ""
    direction = str(direction_raw).lower() if direction_raw else ""
    if direction not in {"inbound", "outbound"}:
        direction = "inbound"

    raw_from = (
        data.get("from_number")
        or data.get("from")
        or data.get("phone_number")
        or data.get("phone")
    )
    raw_to = (
        data.get("to_number")
        or data.get("to")
        or data.get("phone_number")
        or data.get("phone")
    )

    from_number = str(raw_from or settings.twilio_phone_number or "unknown")
    to_number = str(raw_to or from_number or settings.twilio_phone_number or "unknown")

    if not from_number or not to_number:
        _safe_log(
            "error",
            "elevenlabs_call_init_missing_numbers",
            call_sid=call_sid,
            context=context,
            from_number_present=bool(from_number),
            to_number_present=bool(to_number),
        )
        return None
    started_at_ts = data.get("started_at")
    started_at: datetime
    if isinstance(started_at_ts, (int, float)):
        started_at = datetime.fromtimestamp(int(started_at_ts), tz=timezone.utc)
    else:
        started_at = datetime.fromtimestamp(event_timestamp, tz=timezone.utc)
    call = Call(
        call_sid=call_sid,
        direction=direction,
        from_number=str(from_number),
        to_number=str(to_number),
        status="in_progress",
        started_at=started_at,
        handled_by_ai=True,
    )
    db.add(call)
    try:
        await db.flush()
        if not await _commit_with_retry(db, f"{context}_call_init"):
            _safe_log(
                "error",
                "elevenlabs_call_init_commit_failed",
                call_sid=call_sid,
                context=context,
            )
            return None
        _safe_log(
            "info",
            "elevenlabs_call_initialized",
            call_sid=call_sid,
            context=context,
            direction=direction,
            from_number=from_number,
            to_number=to_number,
        )
        return call
    except Exception as e:
        _safe_log(
            "error",
            "elevenlabs_call_init_failed",
            call_sid=call_sid,
            context=context,
            error=str(e),
            error_type=type(e).__name__,
        )
        try:
            await db.rollback()
        except Exception as e2:
            _safe_log(
                "error",
                "elevenlabs_call_init_rollback_failed",
                call_sid=call_sid,
                context=context,
                error=str(e2),
                error_type=type(e2).__name__,
            )
        return None


async def _commit_with_retry(db: AsyncSession, context: str, max_retries: int = 3) -> bool:
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            await db.commit()
            _safe_log("info", "db_commit_success", context=context, attempt=attempt)
            return True
        except Exception as e:
            _safe_log(
                "error",
                "db_commit_failed",
                context=context,
                attempt=attempt,
                error=str(e),
                error_type=type(e).__name__,
            )
            try:
                await db.rollback()
            except Exception as e2:
                _safe_log(
                    "error",
                    "db_rollback_failed",
                    context=context,
                    attempt=attempt,
                    error=str(e2),
                    error_type=type(e2).__name__,
                )
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
    return False


def _parse_signature_header(header_value: str) -> tuple[int | None, list[str]]:
    timestamp: int | None = None
    signatures: list[str] = []
    for part in header_value.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                _safe_log("warning", "elevenlabs_webhook_invalid_timestamp", raw=value)
        elif key in {"v0", "v1", "v2"}:
            signatures.append(value)
    if not signatures and header_value and "=" not in header_value:
        signatures.append(header_value.strip())
    return timestamp, signatures


async def _handle_call_started(
    db: AsyncSession, payload: dict, event_timestamp: int
) -> None:
    if not isinstance(payload, dict):
        _safe_log("error", "elevenlabs_webhook_invalid_payload_type")
        return
    data = payload.get("data") or {}
    event_type = payload.get("type")
    if event_type != "call_started":
        _safe_log("info", "elevenlabs_webhook_ignored_event", event_type=event_type)
        return
    if not isinstance(data, dict):
        _safe_log("error", "elevenlabs_webhook_invalid_data_type", data_type=type(data).__name__)
        return
    call_sid = _extract_call_sid(data)
    if not call_sid:
        _safe_log(
            "warning",
            "elevenlabs_webhook_missing_call_sid",
            event_type=event_type,
            data_keys=list(data.keys()),
        )
        return
    try:
        await db.execute(
            insert(ElevenLabsEventLog).values(
                call_sid=call_sid,
                event_type=event_type,
                event_timestamp=event_timestamp,
                status="processed",
            )
        )
        await db.flush()
    except Exception:
        _safe_log(
            "info",
            "elevenlabs_webhook_duplicate_event",
            call_sid=call_sid,
            event_type=event_type,
            event_timestamp=event_timestamp,
        )
        return
    call = await _ensure_call_initialized(
        db=db,
        call_sid=call_sid,
        data=data,
        event_timestamp=event_timestamp,
        context="call_started",
    )
    if not call:
        _safe_log(
            "error",
            "elevenlabs_call_started_init_failed",
            call_sid=call_sid,
        )
        return


async def _handle_post_call_transcription(
    db: AsyncSession, payload: dict, event_timestamp: int
) -> None:
    if not isinstance(payload, dict):
        _safe_log("error", "elevenlabs_webhook_invalid_payload_type")
        return
    data = payload.get("data") or {}
    event_type = payload.get("type")
    if event_type != "post_call_transcription":
        _safe_log("info", "elevenlabs_webhook_ignored_event", event_type=event_type)
        return
    if not isinstance(data, dict):
        _safe_log("error", "elevenlabs_webhook_invalid_data_type", data_type=type(data).__name__)
        return

    call_sid = _extract_call_sid(data)
    if not call_sid:
        _safe_log(
            "warning",
            "elevenlabs_webhook_missing_call_sid",
            event_type=event_type,
            data_keys=list(data.keys()),
        )
        return

    result = await db.execute(select(Call).where(Call.call_sid == call_sid))
    call = result.scalar_one_or_none()
    if not call:
        _safe_log("warning", "elevenlabs_webhook_call_not_found", call_sid=call_sid)
        return

    now_ts = int(time.time())
    if abs(now_ts - event_timestamp) > 300:
        _safe_log(
            "info",
            "elevenlabs_webhook_transcription_too_old",
            call_sid=call_sid,
            event_timestamp=event_timestamp,
            now=now_ts,
        )
        return

    try:
        await db.execute(
            insert(ElevenLabsEventLog).values(
                call_sid=call_sid,
                event_type=event_type,
                event_timestamp=event_timestamp,
                status="processed",
            )
        )
        await db.flush()
    except Exception:
        _safe_log(
            "info",
            "elevenlabs_webhook_duplicate_event",
            call_sid=call_sid,
            event_type=event_type,
            event_timestamp=event_timestamp,
        )
        return

    transcript, summary = _extract_transcript_and_summary(data)

    conv_id = data.get("conversation_id")
    if isinstance(conv_id, str) and conv_id.strip():
        if not getattr(call, "parent_call_sid", None):
            call.parent_call_sid = conv_id.strip()

    if transcript:
        call.transcript_text = transcript
    if summary:
        call.transcript_summary = summary

    username = _extract_username_from_transcript(transcript)
    if username:
        call.caller_username = username

    if call.status == CallStatus.COMPLETED.value or call.answered_at is not None or bool(transcript):
        call.reception_status = "received"
    else:
        call.reception_status = "not_received"

    if call.reception_timestamp is None:
        call.reception_timestamp = datetime.fromtimestamp(event_timestamp, tz=timezone.utc)

    call.webhook_processed_at = datetime.now(timezone.utc)
    if call.status != CallStatus.COMPLETED.value:
        call.status = CallStatus.COMPLETED.value
    if call.ended_at is None:
        call.ended_at = datetime.fromtimestamp(event_timestamp, tz=timezone.utc)

    await db.flush()
    if not await _commit_with_retry(db, "post_call_transcription"):
        return

    _safe_log(
        "info",
        "elevenlabs_post_call_transcription_processed",
        call_sid=call_sid,
        event_timestamp=event_timestamp,
        has_transcript=bool(transcript),
        has_summary=bool(summary),
    )


async def _handle_post_call_audio(
    db: AsyncSession, payload: dict, event_timestamp: int
) -> None:
    if not isinstance(payload, dict):
        _safe_log("error", "elevenlabs_webhook_invalid_payload_type")
        return
    data = payload.get("data") or {}
    event_type = payload.get("type")
    if event_type != "post_call_audio":
        _safe_log("info", "elevenlabs_webhook_ignored_event", event_type=event_type)
        return
    if not isinstance(data, dict):
        _safe_log("error", "elevenlabs_webhook_invalid_data_type", data_type=type(data).__name__)
        return

    call_sid = _extract_call_sid(data)
    if not call_sid:
        _safe_log(
            "warning",
            "elevenlabs_webhook_missing_call_sid",
            event_type=event_type,
            data_keys=list(data.keys()),
        )
        return

    _safe_log(
        "info",
        "elevenlabs_webhook_audio_event_received",
        call_sid=call_sid,
        event_timestamp=event_timestamp,
    )

    result = await db.execute(select(Call).where(Call.call_sid == call_sid))
    call = result.scalar_one_or_none()

    if not call and call_sid.startswith("conv_"):
        fallback = await db.execute(select(Call).where(Call.parent_call_sid == call_sid))
        call = fallback.scalar_one_or_none()

    if not call:
        call = await _ensure_call_initialized(
            db=db,
            call_sid=call_sid,
            data=data,
            event_timestamp=event_timestamp,
            context="post_call_audio",
        )
        if not call:
            return

    now_ts = int(time.time())
    if abs(now_ts - event_timestamp) > 300:
        _safe_log(
            "info",
            "elevenlabs_webhook_audio_too_old",
            call_sid=call_sid,
            event_timestamp=event_timestamp,
            now=now_ts,
        )
        return

    try:
        await db.execute(
            insert(ElevenLabsEventLog).values(
                call_sid=call_sid,
                event_type=event_type,
                event_timestamp=event_timestamp,
                status="processed",
            )
        )
        await db.flush()
    except Exception:
        _safe_log(
            "info",
            "elevenlabs_webhook_duplicate_event",
            call_sid=call_sid,
            event_type=event_type,
            event_timestamp=event_timestamp,
        )
        return

    recording_url = data.get("recording_url")
    audio_url = data.get("audio_url") or recording_url
    recording_duration = data.get("duration_seconds")

    audio_bytes = b""
    audio_base64 = (
        data.get("audio")
        or data.get("audio_base64")
        or data.get("full_audio")
        or data.get("full_audio_base64")
    )
    if isinstance(audio_base64, str) and audio_base64:
        try:
            audio_bytes = base64.b64decode(audio_base64)
            _safe_log(
                "info",
                "elevenlabs_audio_base64_decoded",
                call_sid=call_sid,
                size=len(audio_bytes),
            )
        except Exception as e:
            _safe_log(
                "error",
                "elevenlabs_audio_base64_decode_failed",
                call_sid=call_sid,
                error=str(e),
                error_type=type(e).__name__,
            )
            return

    if not audio_bytes and audio_url:
        _safe_log(
            "info",
            "elevenlabs_audio_download_start",
            call_sid=call_sid,
            url=audio_url,
        )
        headers = {}
        if settings.elevenlabs_api_key:
            headers["xi-api-key"] = settings.elevenlabs_api_key
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(audio_url, headers=headers)
            if resp.status_code != 200:
                _safe_log(
                    "error",
                    "elevenlabs_audio_download_failed",
                    status_code=resp.status_code,
                    url=audio_url,
                    call_sid=call_sid,
                )
                return
            audio_bytes = resp.content
            _safe_log(
                "info",
                "elevenlabs_audio_download_success",
                call_sid=call_sid,
                url=audio_url,
                size=len(audio_bytes),
            )
        except Exception as e:
            _safe_log(
                "error",
                "elevenlabs_audio_download_exception",
                error=str(e),
                url=audio_url,
                call_sid=call_sid,
                error_type=type(e).__name__,
            )
            return
    else:
        _safe_log("warning", "elevenlabs_webhook_missing_audio_url", call_sid=call_sid)

    blob_url = None
    if audio_bytes:
        _safe_log(
            "info",
            "elevenlabs_audio_blob_upload_start",
            call_sid=call_sid,
            recording_duration=recording_duration,
        )
        date_prefix = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
        file_name = f"elevenlabs/{date_prefix}/{call_sid}_{event_timestamp}.mp3"
        metadata = {
            "source": "elevenlabs",
            "event_type": event_type or "post_call_audio",
            "content_type": "audio/mpeg",
            "call_sid": call_sid,
        }
        blob_service = BlobService()
        blob_url = await blob_service.upload_file(
            file_data=audio_bytes,
            file_name=file_name,
            content_type="audio/mpeg",
            metadata=metadata,
        )
        if not blob_url:
            _safe_log("error", "elevenlabs_audio_blob_upload_failed", call_sid=call_sid, file_name=file_name)
        else:
            _safe_log(
                "info",
                "elevenlabs_audio_blob_upload_success",
                call_sid=call_sid,
                file_name=file_name,
                blob_url=blob_url,
            )

    if blob_url:
        call.recording_url = blob_url
    if recording_duration is not None:
        try:
            call.recording_duration = int(recording_duration)
        except (TypeError, ValueError):
            _safe_log(
                "warning",
                "elevenlabs_webhook_invalid_recording_duration",
                call_sid=call_sid,
                raw=recording_duration,
            )
    call.webhook_processed_at = datetime.now(timezone.utc)
    if call.status != CallStatus.COMPLETED.value:
        call.status = CallStatus.COMPLETED.value
    if call.ended_at is None:
        call.ended_at = datetime.fromtimestamp(event_timestamp, tz=timezone.utc)
    if call.duration_seconds is None and call.recording_duration is not None:
        call.duration_seconds = call.recording_duration

    await db.flush()
    if not await _commit_with_retry(db, "post_call_audio"):
        return

    _safe_log(
        "info",
        "elevenlabs_post_call_audio_processed",
        call_sid=call_sid,
        event_timestamp=event_timestamp,
        has_recording=bool(call.recording_url),
        transcript_generated=False,
    )


@router.post("/webhooks/elevenlabs")
async def elevenlabs_webhook(request: Request) -> dict:
    client_host = request.client.host if request.client and request.client.host else "unknown"
    now = time.time()
    bucket = _elevenlabs_rate_state.get(client_host, [])
    bucket = [ts for ts in bucket if now - ts <= _ELEVENLABS_RATE_WINDOW_SECONDS]
    if len(bucket) >= _ELEVENLABS_RATE_LIMIT:
        _safe_log(
            "warning",
            "elevenlabs_webhook_rate_limited",
            client_host=client_host,
            window_seconds=_ELEVENLABS_RATE_WINDOW_SECONDS,
            limit=_ELEVENLABS_RATE_LIMIT,
        )
        raise HTTPException(status_code=429, detail="Too many ElevenLabs webhook requests")
    bucket.append(now)
    _elevenlabs_rate_state[client_host] = bucket
    secret = settings.elevenlabs_webhook_secret
    if not secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    body = await request.body()
    _safe_log(
        "info",
        "elevenlabs_webhook_request_received",
        content_length=len(body),
        content_type=request.headers.get("content-type"),
        user_agent=request.headers.get("user-agent"),
    )
    signature_header = request.headers.get("elevenlabs-signature") or request.headers.get(
        "ElevenLabs-Signature"
    )
    if not signature_header:
        _safe_log("warning", "elevenlabs_webhook_missing_signature")
        raise HTTPException(status_code=401, detail="Missing ElevenLabs signature")
    timestamp, signatures = _parse_signature_header(signature_header)
    if not signatures:
        _safe_log(
            "warning",
            "elevenlabs_webhook_invalid_signature_format",
            header_length=len(signature_header),
        )
        raise HTTPException(status_code=401, detail="Invalid ElevenLabs signature format")
    if timestamp is not None:
        now = int(time.time())
        if abs(now - timestamp) > 300:
            _safe_log(
                "warning",
                "elevenlabs_webhook_timestamp_out_of_range",
                timestamp=timestamp,
                now=now,
            )
            raise HTTPException(status_code=401, detail="Signature timestamp is too old")
        signed_payload = f"{timestamp}.{body.decode('utf-8')}"
    else:
        signed_payload = body.decode("utf-8")
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected, value) for value in signatures):
        _safe_log(
            "warning",
            "elevenlabs_webhook_invalid_signature",
            header_length=len(signature_header),
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    payload = json.loads(body.decode("utf-8"))
    event_type = payload.get("type")
    event_timestamp = payload.get("event_timestamp")
    _safe_log(
        "info",
        "elevenlabs_webhook_event_validated",
        event_type=event_type,
        event_timestamp=event_timestamp,
        has_signature=bool(signature_header),
    )
    if not event_type or not isinstance(event_timestamp, int):
        _safe_log(
            "warning",
            "elevenlabs_webhook_missing_event_metadata",
            has_type=bool(event_type),
            has_event_timestamp=isinstance(event_timestamp, int),
        )
        return {"success": True}

    async with async_session_maker() as db:
        if event_type == "call_started":
            await _handle_call_started(db, payload, event_timestamp)
        elif event_type == "post_call_transcription":
            await _handle_post_call_transcription(db, payload, event_timestamp)
        elif event_type == "post_call_audio":
            await _handle_post_call_audio(db, payload, event_timestamp)
        else:
            _safe_log("info", "elevenlabs_webhook_ignored_event", event_type=event_type)

    _safe_log(
        "info",
        "elevenlabs_webhook_response_sent",
        event_type=event_type,
        event_timestamp=event_timestamp,
    )
    return {"success": True}
