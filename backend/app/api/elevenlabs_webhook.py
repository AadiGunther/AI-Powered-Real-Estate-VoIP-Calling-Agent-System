"""ElevenLabs webhook endpoints."""

import asyncio
import base64
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import case, func, select
from sqlalchemy import insert as sa_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker
from app.models.call import Call, CallStatus
from app.models.elevenlabs_event_log import ElevenLabsEventLog
from app.models.lead import Lead
from app.services.blob_service import BlobService
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger("elevenlabs_webhook")
try:
    from elevenlabs.client import ElevenLabs
except Exception:
    ElevenLabs = None

try:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
except Exception:
    pg_insert = None

elevenlabs_client = (
    ElevenLabs(api_key=settings.elevenlabs_api_key or "unused") if ElevenLabs else None
)
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


def _is_test_call_sid(call_sid: str) -> bool:
    return str(call_sid).upper().startswith("TEST_")


def _should_ignore_event(call_sid: str, event_type: Optional[str]) -> bool:
    if not call_sid:
        return False
    if _is_test_call_sid(call_sid):
        return True
    if str(event_type or "").strip().lower() == "call_initiation_failure":
        return True
    return False


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
            role_raw = item.get("role") or "unknown"
            # Map 'user' to 'Customer' and 'agent' to 'Agent' for better clarity
            role = "Customer" if str(role_raw).lower() == "user" else str(role_raw).capitalize()
            message = item.get("message")
            if isinstance(message, str) and message:
                parts.append(f"{role}: {message.strip()}")
        transcript_text = "\n".join(parts)
    summary_text = summary_value if isinstance(summary_value, str) else ""
    return transcript_text, summary_text


def _parse_event_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            try:
                dt = datetime.fromtimestamp(int(raw), tz=timezone.utc)
            except Exception:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _normalize_status(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    raw = raw.replace("-", "_")
    if raw == "inprogress":
        raw = "in_progress"
    if raw == "in_progress":
        return CallStatus.IN_PROGRESS.value
    if raw == "completed":
        return CallStatus.COMPLETED.value
    if raw == "ringing":
        return CallStatus.RINGING.value
    if raw == "initiated":
        return CallStatus.INITIATED.value
    return raw


def _verify_elevenlabs_webhook_signature(
    payload_str: str, signature_header: str, secret: str
) -> None:
    tolerance_seconds = 300
    timestamp: Optional[str] = None
    signature: Optional[str] = None
    for part in signature_header.split(","):
        part = part.strip()
        if part.startswith("t="):
            timestamp = part[2:].strip()
        elif part.startswith("v0="):
            signature = part[3:].strip()

    if not timestamp or not signature:
        raise ValueError("Invalid signature header")

    try:
        ts = int(timestamp)
    except Exception:
        raise ValueError("Invalid signature timestamp") from None

    now_ts = int(time.time())
    if abs(now_ts - ts) > tolerance_seconds:
        raise ValueError("Signature timestamp outside tolerance")

    signed_payload = f"{timestamp}.{payload_str}".encode("utf-8")
    secret_clean = str(secret).strip()
    expected = hmac.new(secret_clean.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    provided = signature.strip().lower()
    if provided.startswith("0x"):
        provided = provided[2:]

    if hmac.compare_digest(expected, provided):
        return

    if secret_clean.startswith("wsec_"):
        alt_secret = secret_clean.removeprefix("wsec_")
        alt_expected = hmac.new(alt_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(alt_expected, provided):
            return

    raise ValueError("Invalid signature")


def _extract_username_from_transcript(transcript_text: str) -> Optional[str]:
    if not transcript_text:
        return None
    text = transcript_text.strip()
    if not text:
        return None
    invalid_names = {
        "ditto",
        "same",
        "unknown",
        "na",
        "n/a",
        "none",
        "yes",
        "haan",
        "han",
        "ji",
        "okay",
        "ok",
    }

    patterns = [
        (r"\bmy name is\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})", True),
        (r"\bthis is\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})", True),
        (r"\bhi[, ]+i['’]?m\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})", True),
        (r"\bi am\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})", True),
        (r"\bmera naam\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})\b", True),
        (r"\bnaam\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})\s+hai\b", True),
        (r"\bmain\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2})\s+hoon\b", True),
        (r"मेरा नाम\s+([A-Za-z\u0900-\u097F\s'-]{1,60}?)\s+है", False),
        (r"मैं\s+([A-Za-z\u0900-\u097F\s'-]{1,60}?)\s+हूं", False),
        (r"मेरा नाम\s+([A-Za-z\u0900-\u097F\s'-]{1,60}?)\s+हूँ", False),
    ]

    best: tuple[int, str] | None = None
    trailing_tokens = {"and", "i", "ji", "hai", "hoon", "hun", "haan", "han"}

    for pattern, ignore_case in patterns:
        flags = re.IGNORECASE if ignore_case else 0
        for match in re.finditer(pattern, text, flags):
            candidate = match.group(1).strip()
            cleaned = re.sub(r"[^A-Za-z\u0900-\u097F\s'-]", "", candidate).strip()
            if not cleaned:
                continue

            parts = cleaned.split()
            while parts and parts[-1].lower() in trailing_tokens:
                parts.pop()
            cleaned = " ".join(parts).strip()

            if not cleaned:
                continue
            if cleaned.strip().lower() in invalid_names:
                continue
            if not (1 < len(cleaned) <= 60):
                continue

            if best is None or match.start() > best[0]:
                best = (match.start(), cleaned)

    return best[1] if best else None


def _is_placeholder_name(name: Optional[str]) -> bool:
    if not name:
        return True
    cleaned = name.strip().lower()
    return cleaned in {"ditto", "same", "unknown", "na", "n/a", "none"}


def _normalize_phone(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        value = str(int(value))
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.lower() in {"unknown", "n/a", "none", "null"}:
        return None
    return cleaned


def _normalize_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _collect_call_metadata(data: dict) -> dict:
    collected: dict = {}

    if isinstance(data, dict):
        collected.update(data)

    cid = data.get("conversation_initiation_client_data") if isinstance(data, dict) else None
    if isinstance(cid, dict):
        dyn = cid.get("dynamic_variables")
        if isinstance(dyn, dict):
            collected.update(dyn)
        collected.update(cid)

    meta = data.get("metadata") if isinstance(data, dict) else None
    if isinstance(meta, dict):
        collected.update(meta)

    return collected


def _extract_call_sid_from_meta(meta: dict) -> Optional[str]:
    for key in (
        "call_sid",
        "CallSid",
        "twilio_call_sid",
        "twilioCallSid",
        "external_call_id",
        "externalCallId",
        "call_id",
        "callId",
    ):
        value = _normalize_str(meta.get(key))
        if value:
            return value
    return None


def _extract_first_str(meta: dict, keys: list[str]) -> Optional[str]:
    for key in keys:
        value = meta.get(key)
        cleaned = _normalize_phone(value)
        if cleaned:
            return cleaned
    return None


def _extract_direction(meta: dict) -> str:
    raw = meta.get("direction") or meta.get("call_direction") or ""
    direction = str(raw).lower().strip() if raw else ""
    return direction if direction in {"inbound", "outbound"} else "inbound"


def _derive_call_numbers(meta: dict, direction: str) -> tuple[str, str]:
    twilio_number = _normalize_phone(getattr(settings, "twilio_phone_number", None)) or "unknown"

    explicit_from = _extract_first_str(
        meta, ["from_number", "caller_id", "from", "caller", "source_number"]
    )
    explicit_to = _extract_first_str(
        meta, ["to_number", "called_number", "to", "callee", "destination_number"]
    )
    customer_number = _extract_first_str(meta, ["phone_number", "phone", "customer_number"])

    if explicit_from and explicit_to:
        return explicit_from, explicit_to

    if direction == "outbound":
        from_number = explicit_from or twilio_number
        to_number = explicit_to or customer_number or "unknown"
        if to_number == "unknown" and explicit_from and not explicit_to:
            if explicit_from != twilio_number:
                to_number = explicit_from
            from_number = twilio_number
        return from_number, to_number

    from_number = explicit_from or customer_number or "unknown"
    to_number = explicit_to or twilio_number
    if from_number == "unknown" and explicit_to and not explicit_from:
        if explicit_to != twilio_number:
            from_number = explicit_to
            to_number = twilio_number
    return from_number, to_number


def _maybe_update_call_numbers(call: Call, data: dict) -> bool:
    return False


async def _find_call_by_sid(db: AsyncSession, call_sid: str) -> Optional[Call]:
    result = await db.execute(select(Call).where(Call.call_sid == call_sid))
    call = result.scalar_one_or_none()
    if call:
        return call

    if call_sid.startswith("conv_"):
        result = await db.execute(select(Call).where(Call.parent_call_sid == call_sid))
        return result.scalar_one_or_none()

    return None


async def _upsert_call_by_sid(db: AsyncSession, values: dict) -> Call:
    bind = db.get_bind()
    dialect = bind.dialect.name if bind is not None else ""

    clean_values = {k: v for k, v in values.items() if v is not None}
    clean_values.setdefault("handled_by_ai", True)

    if dialect == "postgresql" and pg_insert is not None:
        insert_stmt = pg_insert(Call).values(**clean_values)

        def coalesce_field(field_name: str):
            return func.coalesce(
                getattr(insert_stmt.excluded, field_name),
                getattr(Call, field_name),
            )

        def preserve_phone_field(field_name: str):
            current = getattr(Call, field_name)
            excluded = getattr(insert_stmt.excluded, field_name)
            return case(
                (
                    (current.is_(None)) | (current == "") | (func.lower(current) == "unknown"),
                    func.coalesce(excluded, current),
                ),
                else_=current,
            )

        def preserve_recording_url_field(field_name: str):
            current = getattr(Call, field_name)
            excluded = getattr(insert_stmt.excluded, field_name)
            container_name = (settings.azure_storage_container_name or "").strip()
            marker = f"/{container_name}/" if container_name else ""
            marker_like = f"%{marker.lower()}%" if marker else ""

            if not marker_like:
                return func.coalesce(excluded, current)

            excluded_has_marker = func.lower(excluded).like(marker_like)
            current_has_marker = func.lower(current).like(marker_like)

            return case(
                (excluded_has_marker, excluded),
                (current_has_marker, current),
                else_=func.coalesce(excluded, current),
            )

        status_expr = case(
            (Call.status == CallStatus.COMPLETED.value, Call.status),
            else_=func.coalesce(insert_stmt.excluded.status, Call.status),
        )

        update_values = {
            "direction": coalesce_field("direction"),
            "from_number": preserve_phone_field("from_number"),
            "to_number": preserve_phone_field("to_number"),
            "parent_call_sid": coalesce_field("parent_call_sid"),
            "status": status_expr,
            "started_at": coalesce_field("started_at"),
            "answered_at": coalesce_field("answered_at"),
            "ended_at": coalesce_field("ended_at"),
            "duration_seconds": coalesce_field("duration_seconds"),
            "recording_url": preserve_recording_url_field("recording_url"),
            "recording_sid": coalesce_field("recording_sid"),
            "recording_duration": coalesce_field("recording_duration"),
            "transcript_text": coalesce_field("transcript_text"),
            "transcript_summary": coalesce_field("transcript_summary"),
            "reception_status": coalesce_field("reception_status"),
            "reception_timestamp": coalesce_field("reception_timestamp"),
            "caller_username": coalesce_field("caller_username"),
            "structured_report": coalesce_field("structured_report"),
            "lead_id": coalesce_field("lead_id"),
            "lead_created": coalesce_field("lead_created"),
            "handled_by_ai": coalesce_field("handled_by_ai"),
            "escalated_to_human": coalesce_field("escalated_to_human"),
            "escalated_to_agent_id": coalesce_field("escalated_to_agent_id"),
            "escalation_reason": coalesce_field("escalation_reason"),
            "sentiment_score": coalesce_field("sentiment_score"),
            "customer_satisfaction": coalesce_field("customer_satisfaction"),
            "webhook_processed_at": coalesce_field("webhook_processed_at"),
            "updated_at": func.now(),
        }

        stmt = (
            insert_stmt.on_conflict_do_update(
                index_elements=[Call.call_sid],
                set_=update_values,
            )
            .returning(Call)
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    existing = await _find_call_by_sid(db, clean_values["call_sid"])
    if existing:
        container_name = (settings.azure_storage_container_name or "").strip()
        marker = f"/{container_name}/" if container_name else ""

        def has_marker(value: object) -> bool:
            return bool(marker) and isinstance(value, str) and marker in value

        for key, value in clean_values.items():
            if key == "call_sid":
                continue
            if key == "status":
                if (
                    getattr(existing, "status", None) == CallStatus.COMPLETED.value
                    and value != CallStatus.COMPLETED.value
                ):
                    continue
            if key in {"from_number", "to_number"}:
                current_norm = str(getattr(existing, key, "") or "").strip().lower()
                if current_norm and current_norm != "unknown":
                    continue
            if key == "recording_url":
                current = getattr(existing, key, None)
                if isinstance(value, str):
                    value = value.strip().strip("`").strip().replace("`", "")

                if has_marker(current) and not has_marker(value):
                    continue
                if has_marker(value) and not has_marker(current):
                    setattr(existing, key, value)
                    continue
                if current:
                    continue
            setattr(existing, key, value)
        return existing

    call = Call(**clean_values)
    db.add(call)
    await db.flush()
    return call


async def _ensure_call_initialized(
    db: AsyncSession,
    call_sid: str,
    data: dict,
    event_timestamp: int,
    context: str,
) -> Optional[Call]:
    call = await _find_call_by_sid(db, call_sid)
    if call:
        return call
    meta = _collect_call_metadata(data)
    if call_sid.startswith("conv_"):
        alt_sid = _extract_call_sid_from_meta(meta)
        if alt_sid and alt_sid != call_sid:
            alt_call = await _find_call_by_sid(db, alt_sid)
            if alt_call:
                if not getattr(alt_call, "parent_call_sid", None):
                    alt_call.parent_call_sid = call_sid
                return alt_call
    direction = _extract_direction(meta)
    from_number, to_number = _derive_call_numbers(meta, direction)

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
    try:
        call = await _upsert_call_by_sid(
            db,
            {
                "call_sid": call_sid,
                "direction": direction,
                "from_number": from_number,
                "to_number": to_number,
                "status": CallStatus.IN_PROGRESS.value,
                "started_at": started_at,
                "handled_by_ai": True,
                "webhook_processed_at": datetime.now(timezone.utc),
            },
        )
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
    if _should_ignore_event(call_sid, event_type):
        _safe_log(
            "info",
            "elevenlabs_webhook_ignored_call",
            call_sid=call_sid,
            event_type=event_type,
        )
        return
    try:
        await db.execute(
            sa_insert(ElevenLabsEventLog).values(
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
    call.webhook_processed_at = datetime.now(timezone.utc)
    await db.flush()
    await _commit_with_retry(db, "call_started")


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
    if _should_ignore_event(call_sid, event_type):
        _safe_log(
            "info",
            "elevenlabs_webhook_ignored_call",
            call_sid=call_sid,
            event_type=event_type,
        )
        return

    call = await _find_call_by_sid(db, call_sid)
    if not call:
        call = await _ensure_call_initialized(
            db=db,
            call_sid=call_sid,
            data=data,
            event_timestamp=event_timestamp,
            context="post_call_transcription",
        )
        if not call:
            _safe_log("warning", "elevenlabs_webhook_call_init_failed", call_sid=call_sid)
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
            sa_insert(ElevenLabsEventLog).values(
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
        if call.lead_id is not None:
            lead_result = await db.execute(select(Lead).where(Lead.id == call.lead_id))
            lead = lead_result.scalar_one_or_none()
            if lead and (not lead.name or lead.name.strip() != username):
                lead.name = username

    if (
        call.status == CallStatus.COMPLETED.value
        or call.answered_at is not None
        or bool(transcript)
    ):
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

    # Trigger Solar Report Generation (Section 7)
    if transcript:
        try:
            from app.models.notification import NotificationType
            from app.models.user import User, UserRole
            from app.services.notification_service import NotificationService
            from app.services.solar_report_service import SolarReportService

            report_service = SolarReportService()
            report = await report_service.generate_report(transcript)
            if report:
                call.structured_report = json.dumps(report, ensure_ascii=False)
                _safe_log("info", "elevenlabs_structured_report_generated", call_sid=call_sid)
                
                # Send notification to managers
                notif_service = NotificationService(db)
                users_res = await db.execute(
                    select(User).where(User.role == UserRole.MANAGER.value)
                )
                managers = users_res.scalars().all()
                
                for manager in managers:
                    await notif_service.create_notification(
                        user_id=manager.id,
                        message=f"📊 Solar Sales Report ready for call {call_sid}",
                        notification_type=NotificationType.CALL_REPORT_GENERATED,
                        related_call_id=call.id,
                        related_lead_id=call.lead_id,
                    )
        except Exception as report_err:
            _safe_log("error", "report_generation_failed", error=str(report_err))

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
    if _should_ignore_event(call_sid, event_type):
        _safe_log(
            "info",
            "elevenlabs_webhook_ignored_call",
            call_sid=call_sid,
            event_type=event_type,
        )
        return

    _safe_log(
        "info",
        "elevenlabs_webhook_audio_event_received",
        call_sid=call_sid,
        event_timestamp=event_timestamp,
    )

    call = await _find_call_by_sid(db, call_sid)

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
            sa_insert(ElevenLabsEventLog).values(
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
            _safe_log(
                "error",
                "elevenlabs_audio_blob_upload_failed",
                call_sid=call_sid,
                file_name=file_name,
            )
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


async def _handle_generic_call_event(
    db: AsyncSession, payload: dict, event_timestamp: int, event_type: str
) -> None:
    if not isinstance(payload, dict):
        return
    data = payload.get("data") or payload
    if not isinstance(data, dict):
        return

    call_sid = _extract_call_sid(data)
    if not call_sid:
        return
    if _should_ignore_event(call_sid, event_type):
        _safe_log(
            "info",
            "elevenlabs_webhook_ignored_call",
            call_sid=call_sid,
            event_type=event_type,
        )
        return

    try:
        await db.execute(
            sa_insert(ElevenLabsEventLog).values(
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

    meta = _collect_call_metadata(data)
    direction = _extract_direction(meta)
    from_number, to_number = _derive_call_numbers(meta, direction)

    transcript, summary = _extract_transcript_and_summary(data)
    audio_url = data.get("audio_url") or data.get("recording_url")
    started_at = _parse_event_datetime(
        data.get("started_at") or data.get("start_timestamp"),
    )
    ended_at = _parse_event_datetime(
        data.get("ended_at") or data.get("end_timestamp"),
    )
    duration = data.get("duration_seconds") or data.get("duration")
    duration_seconds: Optional[int] = None
    if duration is not None:
        try:
            duration_seconds = int(duration)
        except Exception:
            duration_seconds = None

    status_value = _normalize_status(data.get("status"))
    if str(event_type).lower().strip() == "call_completed":
        status_value = CallStatus.COMPLETED.value
        ended_at = ended_at or datetime.fromtimestamp(event_timestamp, tz=timezone.utc)

    await _upsert_call_by_sid(
        db,
        {
            "call_sid": call_sid,
            "direction": direction,
            "from_number": from_number,
            "to_number": to_number,
            "status": status_value,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "transcript_text": transcript or None,
            "transcript_summary": summary or None,
            "recording_url": (
                audio_url if isinstance(audio_url, str) and audio_url.strip() else None
            ),
            "webhook_processed_at": datetime.now(timezone.utc),
            "handled_by_ai": True,
        },
    )
    await db.flush()
    await _commit_with_retry(db, f"generic_{event_type}")



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
    payload_str = body.decode("utf-8")
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
    try:
        _verify_elevenlabs_webhook_signature(payload_str, signature_header, secret)
        payload = json.loads(payload_str)
    except Exception as e:
        _safe_log(
            "warning",
            "elevenlabs_webhook_invalid_signature",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = payload.get("type") or payload.get("event_type")
    raw_event_timestamp = payload.get("event_timestamp")
    event_timestamp: int | None = None
    if isinstance(raw_event_timestamp, (int, float)):
        event_timestamp = int(raw_event_timestamp)
    elif isinstance(raw_event_timestamp, str):
        try:
            event_timestamp = int(raw_event_timestamp)
        except ValueError:
            event_timestamp = None
    _safe_log(
        "info",
        "elevenlabs_webhook_event_validated",
        event_type=event_type,
        event_timestamp=raw_event_timestamp,
        has_signature=bool(signature_header),
    )
    if not event_type or event_timestamp is None:
        _safe_log(
            "warning",
            "elevenlabs_webhook_missing_event_metadata",
            has_type=bool(event_type),
            has_event_timestamp=event_timestamp is not None,
        )
        return {"success": True}

    async with async_session_maker() as db:
        if event_type == "call_started":
            await _handle_call_started(db, payload, event_timestamp)
        elif event_type == "post_call_transcription":
            await _handle_post_call_transcription(db, payload, event_timestamp)
        elif event_type == "post_call_audio":
            await _handle_post_call_audio(db, payload, event_timestamp)
        elif str(event_type).strip().lower() == "call_initiation_failure":
            _safe_log("info", "elevenlabs_webhook_ignored_event", event_type=event_type)
        elif event_type in {
            "call_completed",
            "transcription",
            "summary",
            "audio_available",
        }:
            await _handle_generic_call_event(db, payload, event_timestamp, str(event_type))
        else:
            _safe_log("info", "elevenlabs_webhook_ignored_event", event_type=event_type)

    _safe_log(
        "info",
        "elevenlabs_webhook_response_sent",
        event_type=event_type,
        event_timestamp=event_timestamp,
    )
    return {"success": True}
