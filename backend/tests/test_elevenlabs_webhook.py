import base64
import time

import pytest
from sqlalchemy import select

from app.api.elevenlabs_webhook import (
    _extract_username_from_transcript,
    _handle_post_call_audio,
    _handle_post_call_transcription,
)
from app.api.elevenlabs_webhook import (
    logger as elevenlabs_logger,
)
from app.database import async_session_maker
from app.models.call import Call
from app.models.lead import Lead


@pytest.mark.asyncio
async def test_post_call_transcription_persists_transcript_and_summary(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call_sid = f"EL_ELEVENLABS_TRANSCRIPTION_{int(time.time() * 1000)}"
        call = Call(
            call_sid=call_sid,
            from_number="+10000000000",
            to_number="+19999999999",
        )
        db.add(call)
        await db.commit()

        event_timestamp = int(time.time())
        payload = {
            "type": "post_call_transcription",
            "event_timestamp": event_timestamp,
            "data": {
                "call_id": call_sid,
                "transcript": "hello, my name is John Doe and I have a query.",
                "summary": "short summary",
            },
        }

        await _handle_post_call_transcription(db, payload, event_timestamp)

        result = await db.execute(
            select(Call).where(Call.call_sid == call_sid)
        )
        updated = result.scalar_one()

        assert updated.transcript_text is not None
        assert updated.transcript_summary == "short summary"
        assert updated.webhook_processed_at is not None
        assert updated.reception_status == "received"
        assert updated.reception_timestamp is not None
        assert updated.caller_username in ("John Doe", "John Doe and I")


def test_extract_username_from_transcript_patterns():
    cases = [
        ("hi, I'm Alice from XYZ", "Alice"),
        ("this is Bob Marley calling about a flat", "Bob Marley"),
        ("my name is Charlie", "Charlie"),
        ("I am David Beckham and I was calling", "David Beckham"),
        ("mera naam Ramesh hai", "Ramesh"),
        ("मेरा नाम राहुल है", "राहुल"),
    ]
    for text, expected in cases:
        result = _extract_username_from_transcript(text)
        assert result is not None
        assert expected.split()[0] in result


def test_extract_username_from_transcript_missing_or_invalid():
    assert _extract_username_from_transcript("") is None
    assert _extract_username_from_transcript("no name mentioned here") is None
    assert _extract_username_from_transcript("my name is ditto") is None


@pytest.mark.asyncio
async def test_post_call_transcription_sets_lead_name_from_transcript(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        ts = int(time.time() * 1000)
        lead = Lead(
            name=None,
            phone=f"+1555{ts % 10000000000:010d}",
        )
        db.add(lead)
        await db.flush()

        call_sid = f"EL_ELEVENLABS_TRANSCRIPTION_LEADNAME_{ts}"
        call = Call(
            call_sid=call_sid,
            from_number="+10000000020",
            to_number="+19999999980",
            lead_id=lead.id,
        )
        db.add(call)
        await db.commit()

        event_timestamp = int(time.time())
        payload = {
            "type": "post_call_transcription",
            "event_timestamp": event_timestamp,
            "data": {
                "call_id": call_sid,
                "transcript": "mera naam Ramesh hai",
                "summary": "short summary",
            },
        }

        await _handle_post_call_transcription(db, payload, event_timestamp)

        lead_result = await db.execute(select(Lead).where(Lead.id == lead.id))
        updated_lead = lead_result.scalar_one()
        assert updated_lead.name == "Ramesh"


@pytest.mark.asyncio
async def test_post_call_transcription_uses_conversation_id_and_list_transcript(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call_sid = f"EL_ELEVENLABS_TRANSCRIPTION_CONV_{int(time.time() * 1000)}"
        call = Call(
            call_sid=call_sid,
            from_number="+10000000010",
            to_number="+19999999990",
        )
        db.add(call)
        await db.commit()

        event_timestamp = int(time.time())
        payload = {
            "type": "post_call_transcription",
            "event_timestamp": event_timestamp,
            "data": {
                "conversation_id": call_sid,
                "transcript": [
                    {"role": "agent", "message": "Hello"},
                    {"role": "user", "message": "Hi there"},
                ],
                "analysis": {
                    "transcript_summary": "Short list-based summary",
                },
            },
        }

        await _handle_post_call_transcription(db, payload, event_timestamp)

        result = await db.execute(
            select(Call).where(Call.call_sid == call_sid)
        )
        updated = result.scalar_one()

        assert "Hello" in updated.transcript_text
        assert "Hi there" in updated.transcript_text
        assert updated.transcript_summary == "Short list-based summary"


@pytest.mark.asyncio
async def test_post_call_transcription_falls_back_to_parent_call_sid(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        ts = int(time.time() * 1000)
        twilio_sid = f"EL_ELEVENLABS_TRANSCRIPTION_TWILIO_{ts}"
        conversation_id = f"conv_{ts}"
        call = Call(
            call_sid=twilio_sid,
            parent_call_sid=conversation_id,
            from_number="+10000000011",
            to_number="+19999999989",
        )
        db.add(call)
        await db.commit()

        event_timestamp = int(time.time())
        payload = {
            "type": "post_call_transcription",
            "event_timestamp": event_timestamp,
            "data": {
                "conversation_id": conversation_id,
                "transcript": "hello from conversation id",
                "summary": "sum",
            },
        }

        await _handle_post_call_transcription(db, payload, event_timestamp)

        result = await db.execute(select(Call).where(Call.call_sid == twilio_sid))
        updated = result.scalar_one()

        assert updated.transcript_text == "hello from conversation id"
        assert updated.transcript_summary == "sum"


@pytest.mark.asyncio
async def test_post_call_transcription_not_broken_by_logging_failure(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call_sid = f"EL_ELEVENLABS_TRANSCRIPTION_LOGGING_{int(time.time() * 1000)}"
        call = Call(
            call_sid=call_sid,
            from_number="+10000000001",
            to_number="+19999999998",
        )
        db.add(call)
        await db.commit()

        def failing_info(event, **kwargs):
            raise RuntimeError("logging failure")

        monkeypatch.setattr(elevenlabs_logger, "info", failing_info)

        event_timestamp = int(time.time())
        payload = {
            "type": "post_call_transcription",
            "event_timestamp": event_timestamp,
            "data": {
                "call_id": call_sid,
                "transcript": "text",
                "summary": "sum",
            },
        }

        await _handle_post_call_transcription(db, payload, event_timestamp)

        result = await db.execute(
            select(Call).where(Call.call_sid == call_sid)
        )
        updated = result.scalar_one()

        assert updated.transcript_text == "text"
        assert updated.transcript_summary == "sum"


@pytest.mark.asyncio
async def test_post_call_audio_persists_recording_and_handles_blob_upload(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call_sid = f"EL_ELEVENLABS_AUDIO_{int(time.time() * 1000)}"
        call = Call(
            call_sid=call_sid,
            from_number="+10000000002",
            to_number="+19999999997",
        )
        db.add(call)
        await db.commit()

        class DummyResponse:
            def __init__(self):
                self.status_code = 200
                self.content = b"fake-audio-bytes"

        async def dummy_get(url, headers=None):
            return DummyResponse()

        class DummyClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, headers=None):
                return await dummy_get(url, headers=headers)

        monkeypatch.setattr("app.api.elevenlabs_webhook.httpx.AsyncClient", DummyClient)

        async def dummy_upload_file(
            self, file_data, file_name, content_type="audio/mpeg", metadata=None
        ):
            return f"https://blob.example.com/{file_name}"

        monkeypatch.setattr(
            "app.api.elevenlabs_webhook.BlobService.upload_file",
            dummy_upload_file,
        )

        event_timestamp = int(time.time())
        payload = {
            "type": "post_call_audio",
            "event_timestamp": event_timestamp,
            "data": {
                "call_id": call_sid,
                "audio_url": "https://example.com/audio.mp3",
                "duration_seconds": 42,
            },
        }

        await _handle_post_call_audio(db, payload, event_timestamp)

        result = await db.execute(
            select(Call).where(Call.call_sid == call_sid)
        )
        updated = result.scalar_one()

        assert updated.recording_url is not None
        assert updated.recording_duration == 42
        assert updated.webhook_processed_at is not None


@pytest.mark.asyncio
async def test_post_call_audio_handles_full_audio_base64(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call_sid = f"EL_ELEVENLABS_FULL_AUDIO_{int(time.time() * 1000)}"
        call = Call(
            call_sid=call_sid,
            from_number="+10000000003",
            to_number="+19999999996",
        )
        db.add(call)
        await db.commit()

        async def dummy_upload_file(
            self, file_data, file_name, content_type="audio/mpeg", metadata=None
        ):
            return f"https://blob.example.com/{file_name}"

        monkeypatch.setattr(
            "app.api.elevenlabs_webhook.BlobService.upload_file",
            dummy_upload_file,
        )

        event_timestamp = int(time.time())
        audio_bytes = b"fake-audio-full"
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        payload = {
            "type": "post_call_audio",
            "event_timestamp": event_timestamp,
            "data": {
                "call_id": call_sid,
                "full_audio": audio_b64,
                "duration_seconds": 30,
            },
        }

        await _handle_post_call_audio(db, payload, event_timestamp)

        result = await db.execute(
            select(Call).where(Call.call_sid == call_sid)
        )
        updated = result.scalar_one()

        assert updated.recording_url is not None
        assert updated.recording_duration == 30
        assert updated.webhook_processed_at is not None
