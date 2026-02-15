import time

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.call import Call
from app.api.elevenlabs_webhook import (
    _handle_post_call_transcription,
    _handle_post_call_audio,
    logger as elevenlabs_logger,
)


@pytest.mark.asyncio
async def test_post_call_transcription_persists_transcript_and_summary(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call = Call(
            call_sid="TEST_ELEVENLABS_TRANSCRIPTION",
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
                "call_id": "TEST_ELEVENLABS_TRANSCRIPTION",
                "transcript": "hello world transcript",
                "summary": "short summary",
            },
        }

        await _handle_post_call_transcription(db, payload, event_timestamp)

        result = await db.execute(
            select(Call).where(Call.call_sid == "TEST_ELEVENLABS_TRANSCRIPTION")
        )
        updated = result.scalar_one()

        assert updated.transcript_text == "hello world transcript"
        assert updated.transcript_summary == "short summary"
        assert updated.webhook_processed_at is not None


@pytest.mark.asyncio
async def test_post_call_transcription_uses_conversation_id_and_list_transcript(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call = Call(
            call_sid="TEST_ELEVENLABS_TRANSCRIPTION_CONV",
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
                "conversation_id": "TEST_ELEVENLABS_TRANSCRIPTION_CONV",
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
            select(Call).where(Call.call_sid == "TEST_ELEVENLABS_TRANSCRIPTION_CONV")
        )
        updated = result.scalar_one()

        assert "Hello" in updated.transcript_text
        assert "Hi there" in updated.transcript_text
        assert updated.transcript_summary == "Short list-based summary"


@pytest.mark.asyncio
async def test_post_call_transcription_not_broken_by_logging_failure(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call = Call(
            call_sid="TEST_ELEVENLABS_TRANSCRIPTION_LOGGING",
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
                "call_id": "TEST_ELEVENLABS_TRANSCRIPTION_LOGGING",
                "transcript": "text",
                "summary": "sum",
            },
        }

        await _handle_post_call_transcription(db, payload, event_timestamp)

        result = await db.execute(
            select(Call).where(Call.call_sid == "TEST_ELEVENLABS_TRANSCRIPTION_LOGGING")
        )
        updated = result.scalar_one()

        assert updated.transcript_text == "text"
        assert updated.transcript_summary == "sum"


@pytest.mark.asyncio
async def test_post_call_audio_persists_recording_and_handles_blob_upload(monkeypatch):
    async with async_session_maker() as db:  # type: AsyncSession
        call = Call(
            call_sid="TEST_ELEVENLABS_AUDIO",
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

        async def dummy_upload_file(file_data, file_name, content_type="audio/mpeg", metadata=None):
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
                "call_id": "TEST_ELEVENLABS_AUDIO",
                "audio_url": "https://example.com/audio.mp3",
                "duration_seconds": 42,
            },
        }

        await _handle_post_call_audio(db, payload, event_timestamp)

        result = await db.execute(
            select(Call).where(Call.call_sid == "TEST_ELEVENLABS_AUDIO")
        )
        updated = result.scalar_one()

        assert updated.recording_url is not None
        assert updated.recording_duration == 42
        assert updated.webhook_processed_at is not None
