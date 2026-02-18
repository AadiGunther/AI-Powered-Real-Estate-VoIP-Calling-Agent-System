import asyncio
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import async_session_maker
from app.main import app
from app.models.call import Call
from app.models.elevenlabs_event_log import ElevenLabsEventLog

client = TestClient(app)


def build_signature_header(body: bytes, secret: str, timestamp: str) -> str:
    signed_payload = f"{timestamp}.{body.decode('utf-8')}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v0={signature}"


async def _create_call(call_sid: str) -> None:
    async with async_session_maker() as db:
        call = Call(
            call_sid=call_sid,
            direction="inbound",
            from_number="+10000000000",
            to_number="+12223334444",
            status="completed",
        )
        db.add(call)
        await db.commit()


def test_transcription_webhook_idempotent(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    call_sid = f"EL_ELEVENLABS_IDEMPOTENT_{int(time.time() * 1000)}"

    asyncio.get_event_loop().run_until_complete(_create_call(call_sid))

    payload = {
        "type": "post_call_transcription",
        "event_timestamp": int(time.time()),
        "data": {
            "call_id": call_sid,
            "transcript": "Hello world",
            "summary": "Summary",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)

    for _ in range(3):
        response = client.post(
            "/webhooks/elevenlabs",
            data=body,
            headers={
                "content-type": "application/json",
                "elevenlabs-signature": signature_header,
            },
        )
        assert response.status_code == 200

    async def _assert_db():
        async with async_session_maker() as db:
            result = await db.execute(
                select(Call).where(Call.call_sid == call_sid)
            )
            call = result.scalar_one()
            assert call.transcript_text == "Hello world"
            assert call.transcript_summary == "Summary"

            result_events = await db.execute(
                select(ElevenLabsEventLog).where(
                    ElevenLabsEventLog.call_sid == call_sid,
                    ElevenLabsEventLog.event_type == "post_call_transcription",
                )
            )
            events = result_events.scalars().all()
            assert len(events) == 1

    asyncio.get_event_loop().run_until_complete(_assert_db())


def test_call_started_creates_call_record(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    call_sid = f"EL_ELEVENLABS_CALL_STARTED_{int(time.time() * 1000)}"

    payload = {
        "type": "call_started",
        "event_timestamp": int(time.time()),
        "data": {
            "conversation_id": call_sid,
            "from_number": "+15550001111",
            "to_number": "+15550002222",
            "direction": "outbound",
            "started_at": int(time.time()),
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)

    response = client.post(
        "/webhooks/elevenlabs",
        data=body,
        headers={
            "content-type": "application/json",
            "elevenlabs-signature": signature_header,
        },
    )
    assert response.status_code == 200

    async def _assert_db():
        async with async_session_maker() as db:
            result = await db.execute(select(Call).where(Call.call_sid == call_sid))
            call = result.scalar_one()
            assert call.from_number == "+15550001111"
            assert call.to_number == "+15550002222"
            assert call.direction == "outbound"
            assert call.status == "in_progress"

            result_events = await db.execute(
                select(ElevenLabsEventLog).where(
                    ElevenLabsEventLog.call_sid == call_sid,
                    ElevenLabsEventLog.event_type == "call_started",
                )
            )
            events = result_events.scalars().all()
            assert len(events) == 1

    asyncio.get_event_loop().run_until_complete(_assert_db())


def test_test_call_sid_is_ignored(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    call_sid = f"TEST_ELEVENLABS_IGNORED_{int(time.time() * 1000)}"
    payload = {
        "type": "call_started",
        "event_timestamp": int(time.time()),
        "data": {
            "conversation_id": call_sid,
            "from_number": "+15550001111",
            "to_number": "+15550002222",
            "direction": "outbound",
            "started_at": int(time.time()),
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)

    response = client.post(
        "/webhooks/elevenlabs",
        data=body,
        headers={
            "content-type": "application/json",
            "elevenlabs-signature": signature_header,
        },
    )
    assert response.status_code == 200

    async def _assert_db():
        async with async_session_maker() as db:
            result = await db.execute(select(Call).where(Call.call_sid == call_sid))
            assert result.scalar_one_or_none() is None

            result_events = await db.execute(
                select(ElevenLabsEventLog).where(ElevenLabsEventLog.call_sid == call_sid)
            )
            assert result_events.scalars().all() == []

    asyncio.get_event_loop().run_until_complete(_assert_db())


def test_call_initiation_failure_is_ignored(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    call_sid = f"EL_ELEVENLABS_FAILURE_{int(time.time() * 1000)}"
    payload = {
        "type": "call_initiation_failure",
        "event_timestamp": int(time.time()),
        "data": {
            "call_id": call_sid,
            "status": "failed",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)

    response = client.post(
        "/webhooks/elevenlabs",
        data=body,
        headers={
            "content-type": "application/json",
            "elevenlabs-signature": signature_header,
        },
    )
    assert response.status_code == 200

    async def _assert_db():
        async with async_session_maker() as db:
            result = await db.execute(select(Call).where(Call.call_sid == call_sid))
            assert result.scalar_one_or_none() is None

    asyncio.get_event_loop().run_until_complete(_assert_db())


def test_webhook_does_not_override_existing_from_to_numbers(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    call_sid = f"EL_ELEVENLABS_PRESERVE_NUMBERS_{int(time.time() * 1000)}"

    expected_from = "+15550001111"
    expected_to = "+15550002222"

    async def _seed_call():
        async with async_session_maker() as db:
            db.add(
                Call(
                    call_sid=call_sid,
                    direction="outbound",
                    from_number=expected_from,
                    to_number=expected_to,
                    status="in_progress",
                )
            )
            await db.commit()

    asyncio.get_event_loop().run_until_complete(_seed_call())

    payload = {
        "type": "call_completed",
        "event_timestamp": int(time.time()),
        "data": {
            "call_id": call_sid,
            "direction": "outbound",
            "from_number": "+19990000000",
            "to_number": "+18880000000",
            "status": "completed",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)

    response = client.post(
        "/webhooks/elevenlabs",
        data=body,
        headers={
            "content-type": "application/json",
            "elevenlabs-signature": signature_header,
        },
    )
    assert response.status_code == 200

    async def _assert_db():
        async with async_session_maker() as db:
            result = await db.execute(select(Call).where(Call.call_sid == call_sid))
            call = result.scalar_one()
            assert call.from_number == expected_from
            assert call.to_number == expected_to

    asyncio.get_event_loop().run_until_complete(_assert_db())
