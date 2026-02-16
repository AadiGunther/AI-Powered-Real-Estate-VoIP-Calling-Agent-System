import json
import hmac
import hashlib
import time

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


client = TestClient(app)


def build_signature_header(body: bytes, secret: str, timestamp: str) -> str:
    signed_payload = f"{timestamp}.{body.decode('utf-8')}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def test_elevenlabs_webhook_valid_signature(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    payload = {
        "type": "post_call_transcription",
        "data": {},
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
    assert response.json() == {"success": True}


def test_elevenlabs_webhook_invalid_signature(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    payload = {
        "type": "post_call_transcription",
        "data": {},
    }
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature_header = build_signature_header(body, secret, timestamp)
    bad_header = signature_header.replace("v1=", "v1=0")

    response = client.post(
        "/webhooks/elevenlabs",
        data=body,
        headers={
            "content-type": "application/json",
            "elevenlabs-signature": bad_header,
        },
    )

    assert response.status_code == 401


def test_elevenlabs_webhook_rate_limit(monkeypatch):
    secret = settings.elevenlabs_webhook_secret or "test-secret"
    monkeypatch.setattr(settings, "elevenlabs_webhook_secret", secret)

    from app.api import elevenlabs_webhook as webhook_module

    webhook_module._elevenlabs_rate_state.clear()
    monkeypatch.setattr(webhook_module, "_ELEVENLABS_RATE_LIMIT", 3)

    payload = {
        "type": "post_call_transcription",
        "event_timestamp": int(time.time()),
        "data": {},
    }
    body = json.dumps(payload).encode("utf-8")

    def make_headers():
        ts = str(int(time.time()))
        sig = hmac.new(
            secret.encode("utf-8"),
            f"{ts}.{body.decode('utf-8')}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "content-type": "application/json",
            "elevenlabs-signature": f"t={ts},v1={sig}",
        }

    for _ in range(3):
        response = client.post("/webhooks/elevenlabs", data=body, headers=make_headers())
        assert response.status_code == 200

    response = client.post("/webhooks/elevenlabs", data=body, headers=make_headers())
    assert response.status_code == 429
