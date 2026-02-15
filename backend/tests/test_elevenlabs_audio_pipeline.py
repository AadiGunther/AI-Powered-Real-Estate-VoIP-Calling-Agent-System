import json
import hmac
import hashlib
import time

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.config import settings
from app.database import async_session_maker
from app.models.call import Call


client = TestClient(app)


def build_signature_header(body: bytes, secret: str, timestamp: str) -> str:
    signed_payload = f"{timestamp}.{body.decode('utf-8')}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


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


def test_audio_webhook_persists_to_blob_and_generates_transcript(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    fake_blob_url = "https://example.blob.core.windows.net/container/audio.mp3"
    audio_bytes = b"fake-binary-audio"

    class DummyBlobService:
        async def upload_file(self, file_data, file_name, content_type="audio/mpeg", metadata=None, max_retries=3):
            assert file_data == audio_bytes
            assert "elevenlabs" in file_name
            return fake_blob_url

    class DummySTTService:
        async def transcribe_audio(self, audio_bytes_param, file_name="audio.wav"):
            assert audio_bytes_param == audio_bytes
            return "This is a transcribed sentence"

    async def dummy_generate_report(call_sid, transcript, transcript_messages=None):
        assert transcript == "This is a transcribed sentence"

    from app.api import elevenlabs_webhook as webhook_module

    monkeypatch.setattr(webhook_module, "BlobService", DummyBlobService)
    monkeypatch.setattr(webhook_module, "STTService", DummySTTService)
    monkeypatch.setattr(
        webhook_module.ReportService,
        "generate_report",
        dummy_generate_report,
    )

    call_sid = "TEST_ELEVENLABS_AUDIO_PIPELINE"

    import asyncio

    asyncio.get_event_loop().run_until_complete(_create_call(call_sid))

    payload = {
        "type": "post_call_audio",
        "event_timestamp": int(time.time()),
        "data": {
            "call_id": call_sid,
            "audio_url": "https://api.elevenlabs.io/v1/audio/fake",
            "duration_seconds": 42,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)

    import httpx

    class DummyResponse:
        def __init__(self, status_code: int, content: bytes):
            self.status_code = status_code
            self.content = content

    class DummyAsyncClient:
        def __init__(self, timeout: float = 60.0):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def get(self, url, headers=None):
            return DummyResponse(200, audio_bytes)

    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)

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
            assert call.recording_url == fake_blob_url
            assert call.recording_duration == 42
            assert call.transcript_text == "This is a transcribed sentence"

    asyncio.get_event_loop().run_until_complete(_assert_db())


def test_audio_webhook_supports_conversation_id_and_base64(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    fake_blob_url = "https://example.blob.core.windows.net/container/audio2.mp3"
    audio_bytes = b"fake-binary-audio-2"

    class DummyBlobService:
        async def upload_file(self, file_data, file_name, content_type="audio/mpeg", metadata=None, max_retries=3):
            assert file_data == audio_bytes
            assert "elevenlabs" in file_name
            return fake_blob_url

    class DummySTTService:
        async def transcribe_audio(self, audio_bytes_param, file_name="audio.wav"):
            assert audio_bytes_param == audio_bytes
            return "Another transcribed sentence"

    async def dummy_generate_report(call_sid, transcript, transcript_messages=None):
        assert transcript == "Another transcribed sentence"

    from app.api import elevenlabs_webhook as webhook_module

    monkeypatch.setattr(webhook_module, "BlobService", DummyBlobService)
    monkeypatch.setattr(webhook_module, "STTService", DummySTTService)
    monkeypatch.setattr(
        webhook_module.ReportService,
        "generate_report",
        dummy_generate_report,
    )

    call_sid = "TEST_ELEVENLABS_AUDIO_PIPELINE_CONV"

    import asyncio

    asyncio.get_event_loop().run_until_complete(_create_call(call_sid))

    import base64 as _b64

    payload = {
        "type": "post_call_audio",
        "event_timestamp": int(time.time()),
        "data": {
            "conversation_id": call_sid,
            "audio": _b64.b64encode(audio_bytes).decode("ascii"),
            "duration_seconds": 55,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)

    import httpx

    class DummyResponse:
        def __init__(self, status_code: int, content: bytes):
            self.status_code = status_code
            self.content = content

    class DummyAsyncClient:
        def __init__(self, timeout: float = 60.0):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def get(self, url, headers=None):
            return DummyResponse(200, audio_bytes)

    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)

    response = client.post(
        "/webhooks/elevenlabs",
        data=body,
        headers={
            "content-type": "application/json",
            "elevenlabs-signature": signature_header,
        },
    )
    assert response.status_code == 200

    async def _assert_db2():
        async with async_session_maker() as db:
            result = await db.execute(select(Call).where(Call.call_sid == call_sid))
            call = result.scalar_one()
            assert call.recording_url == fake_blob_url
            assert call.recording_duration == 55
            assert call.transcript_text == "Another transcribed sentence"

    asyncio.get_event_loop().run_until_complete(_assert_db2())


def test_audio_webhook_creates_call_if_missing(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    fake_blob_url = "https://example.blob.core.windows.net/container/audio3.mp3"
    audio_bytes = b"fake-binary-audio-3"

    class DummyBlobService:
        async def upload_file(self, file_data, file_name, content_type="audio/mpeg", metadata=None, max_retries=3):
            assert file_data == audio_bytes
            assert "elevenlabs" in file_name
            return fake_blob_url

    class DummySTTService:
        async def transcribe_audio(self, audio_bytes_param, file_name="audio.wav"):
            assert audio_bytes_param == audio_bytes
            return "Pipeline-created transcript"

    async def dummy_generate_report(call_sid, transcript, transcript_messages=None):
        assert transcript == "Pipeline-created transcript"

    from app.api import elevenlabs_webhook as webhook_module

    monkeypatch.setattr(webhook_module, "BlobService", DummyBlobService)
    monkeypatch.setattr(webhook_module, "STTService", DummySTTService)
    monkeypatch.setattr(
        webhook_module.ReportService,
        "generate_report",
        dummy_generate_report,
    )

    call_sid = "TEST_ELEVENLABS_AUDIO_PIPELINE_AUTO_CALL"

    import asyncio

    import base64 as _b64

    payload = {
        "type": "post_call_audio",
        "event_timestamp": int(time.time()),
        "data": {
            "conversation_id": call_sid,
            "from_number": "+15550003333",
            "to_number": "+15550004444",
            "direction": "inbound",
            "audio": _b64.b64encode(audio_bytes).decode("ascii"),
            "duration_seconds": 33,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)

    import httpx

    class DummyResponse:
        def __init__(self, status_code: int, content: bytes):
            self.status_code = status_code
            self.content = content

    class DummyAsyncClient:
        def __init__(self, timeout: float = 60.0):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def get(self, url, headers=None):
            return DummyResponse(200, audio_bytes)

    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)

    response = client.post(
        "/webhooks/elevenlabs",
        data=body,
        headers={
            "content-type": "application/json",
            "elevenlabs-signature": signature_header,
        },
    )
    assert response.status_code == 200

    async def _assert_db3():
        async with async_session_maker() as db:
            result = await db.execute(select(Call).where(Call.call_sid == call_sid))
            call = result.scalar_one()
            assert call.from_number == "+15550003333"
            assert call.to_number == "+15550004444"
            assert call.direction == "inbound"
            assert call.recording_url == fake_blob_url
            assert call.recording_duration == 33
            assert call.transcript_text == "Pipeline-created transcript"

    asyncio.get_event_loop().run_until_complete(_assert_db3())
