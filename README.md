# AI-Powered Real Estate VoIP Calling Agent System

Production-grade VoIP calling system for ABC Real Estate using Twilio Media Streams, FastAPI, React TypeScript, Azure OpenAI GPT-4.1, and Deepgram.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         React Frontend                           │
│  Dashboard │ Properties │ Leads │ Calls │ Reports │ Admin        │
└─────────────────────────────┬────────────────────────────────────┘
                              │ REST API
┌─────────────────────────────▼────────────────────────────────────┐
│                        FastAPI Backend                            │
├──────────────────────────────────────────────────────────────────┤
│  /auth/*  │  /properties/*  │  /leads/*  │  /calls/*  │ /admin/* │
├──────────────────────────────────────────────────────────────────┤
│                      VoIP Audio Pipeline                          │
│  Twilio WebSocket → STT (Deepgram) → GPT-4.1 → TTS (Deepgram)    │
└──────────────────────────────┬───────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         SQLite DB/PostgreSQL        MongoDB          Twilio
        (SQL Data)                (Transcripts)      (VoIP)
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB (local or Docker)
- Twilio Account
- Deepgram API Key
- Azure OpenAI API Key

### 1. Clone and Setup

```bash
cd "VOP AI"

# Backend setup
cd backend
cp .env.example .env
# Edit .env with your API keys

poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
npm run lint
npm run typecheck
npm test
```

### 2. Using Docker

```bash
# Copy environment template
cp backend/.env.example .env

# Start all services
docker-compose up -d

# Access:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

## 📁 Project Structure

```
VOP AI/
├── backend/
│   ├── app/
│   │   ├── api/           # REST API endpoints
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   ├── voip/          # VoIP audio pipeline
│   │   ├── middleware/    # Auth middleware
│   │   ├── utils/         # Utilities
│   │   ├── config.py      # Settings
│   │   ├── database.py    # DB connections
│   │   └── main.py        # FastAPI app
│   ├── alembic/           # DB migrations
│   └── tests/             # Test files
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API services
│   │   ├── store/         # Zustand state
│   │   ├── types/         # TypeScript types
│   │   └── styles/        # CSS
│   └── public/
└── docker-compose.yml
```

## 🔧 Configuration

### Required Environment Variables

```env
# Twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Deepgram
DEEPGRAM_API_KEY=your_deepgram_key

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_DEPLOYMENT=gpt-4

# JWT
JWT_SECRET_KEY=your-secret-key-min-32-chars
```

### Twilio Webhook Setup

Configure these webhooks in Twilio console:
- **Voice Webhook**: `https://your-domain.com/twilio/webhook` (POST)
- **Status Callback**: `https://your-domain.com/twilio/status` (POST)

## 📞 VoIP Pipeline

1. **Incoming Call** → Twilio webhook creates call record
2. **Media Stream** → Twilio connects WebSocket
3. **Audio Buffer** → Accumulates audio chunks (500ms)
4. **STT** → Deepgram transcribes speech (streaming)
5. **Turn Detection** → Detects user finished speaking
6. **AI Agent** → GPT-4.1 generates response with function calling
7. **TTS** → Deepgram synthesizes speech
8. **Response** → Audio sent back via WebSocket

## ElevenLabs Post-Call Webhooks for Recording Persistence

This project integrates ElevenLabs post-call webhooks to persist both:

- Full call recordings (MP3) in Azure Blob Storage, and
- Conversation transcripts and summaries on the `Call` record in the database.

All ElevenLabs post-call webhooks are handled by the FastAPI endpoint:

- `POST https://<backend-domain>/webhooks/elevenlabs`

The implementation follows the ElevenLabs post-call webhook specification and is designed to safely handle additional fields introduced by future schema updates.

### Required Configuration and Environment Variables

The following environment variables must be set in `backend/.env`:

```env
# ElevenLabs core configuration
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_WEBHOOK_SECRET=your_webhook_signing_secret  # wsec_...

# Azure Blob Storage for call recordings
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
AZURE_STORAGE_CONTAINER_NAME=call-recordings-or-your-container-name
```

- `ELEVENLABS_WEBHOOK_SECRET` is the HMAC secret configured in the ElevenLabs dashboard for the webhook.
- `ELEVENLABS_API_KEY` is optional for webhooks but is used if the backend needs to download audio from an `audio_url` provided by ElevenLabs.
- The Azure Storage variables are used by `BlobService` to upload the final MP3 recording.

### Webhook URL and ElevenLabs Configuration

1. In the ElevenLabs dashboard, open your agent or workspace settings.
2. Enable **Post-call webhooks**.
3. Configure the webhook URL:
   - `https://<backend-domain>/webhooks/elevenlabs`
4. Set the **HMAC secret** to match `ELEVENLABS_WEBHOOK_SECRET` in your backend `.env`.
5. Enable at least the following webhook types:
   - `post_call_transcription` – for full transcript and analysis.
   - `post_call_audio` – for final full-call audio (base64 or URL).
6. Save and, if available, use the “Send test webhook” feature in ElevenLabs to validate the integration.

> Note: ElevenLabs considers a webhook delivery successful only if your endpoint returns HTTP 200. Repeated failures can cause webhooks to be disabled on their side.

### Authentication and Signature Verification

The `/webhooks/elevenlabs` endpoint validates all incoming requests using HMAC signatures, based on the ElevenLabs specification.

- ElevenLabs sends an `elevenlabs-signature` header (aliases: `ElevenLabs-Signature` also accepted).
- The header uses a comma-separated format:

  ```text
  elevenlabs-signature: t=<unix_timestamp>,v1=<hex_hmac>
  ```

- The backend:
  1. Parses the header to extract the timestamp (`t`) and one or more `v1` signature values.
  2. Rejects requests with missing or malformed signatures (HTTP 401).
  3. Rejects requests with timestamps older than 5 minutes (HTTP 401).
  4. Computes the expected HMAC using:

     ```text
     signed_payload = "<timestamp>.<raw_body>"
     expected = HMAC_SHA256(ELEVENLABS_WEBHOOK_SECRET, signed_payload)
     ```

  5. Compares `expected` against provided `v1` values using constant-time comparison.
  6. Only if a match is found is the request accepted and processed.

If authentication fails, the endpoint returns `401` and does not attempt to process or persist any data.

### Request Payloads and Event Types

ElevenLabs sends different post-call webhook types; this project explicitly handles:

- `call_started` – used to initialize or update the `Call` record.
- `post_call_transcription` – contains full conversation transcript, summary, and analysis.
- `post_call_audio` – contains base64-encoded audio or a URL to the final call recording plus metadata.

All webhook payloads share a common top-level structure:

```json
{
  "type": "post_call_audio",
  "event_timestamp": 1734500000,
  "data": {
    "...": "event-specific fields"
  }
}
```

- `type` is one of `call_started`, `post_call_transcription`, `post_call_audio`, or other event types that may be added by ElevenLabs.
- `event_timestamp` is a Unix timestamp used for idempotency, ordering, and recency checks.
- `data` contains event-specific fields.

The backend is designed to safely ignore unknown top-level or nested fields, so the integration continues to work even as ElevenLabs adds more metadata (for example, boolean flags like `has_audio`, `has_user_audio`, `has_response_audio` in the transcription payload).

#### `post_call_audio` – Recording Persistence

For `post_call_audio` events, the backend expects a payload similar to:

```json
{
  "type": "post_call_audio",
  "event_timestamp": 1734500000,
  "data": {
    "call_id": "conv_abc123",
    "audio": "BASE64_AUDIO_STRING",        // optional
    "audio_url": "https://...",            // optional alternative
    "duration_seconds": 123
  }
}
```

Backend behavior:

1. **Call identification**
   - Extracts a `call_sid` from `data` using several key candidates (`call_id`, `external_id`, `conversation_id`, etc.).
   - Looks up the corresponding `Call` row in the database; if not found and the ID looks like a conversation ID, it may map it to an existing call via `parent_call_sid` or initialize a new call record.

2. **Idempotency and recency**
   - Stores an entry in `ElevenLabsEventLog` keyed by `(call_sid, event_type, event_timestamp)`.
   - If a duplicate event is received, it is logged and ignored.
   - Events older than a configured window (5 minutes by default) are ignored to avoid late or replayed events.

3. **Audio retrieval**
   - If `data.audio` or `data.audio_base64` is present, it decodes the base64 data into raw bytes.
   - Otherwise, if `audio_url` or `recording_url` is present, it:
     - Issues an authenticated HTTP GET using `ELEVENLABS_API_KEY` if required.
     - Validates that the response status is `200`.
     - Reads the response body as audio bytes.

4. **Upload to Azure Blob Storage**
   - Uses `BlobService` with `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_STORAGE_CONTAINER_NAME`.
   - Constructs a file name like:

     ```text
     elevenlabs/YYYY-MM-DD/<call_sid>_<event_timestamp>.mp3
     ```

   - Uploads the audio bytes with metadata (`source=elevenlabs`, `event_type=post_call_audio`, `call_sid=<call_sid>`).
   - On success, obtains a public or signed `blob_url` pointing to the recording.

5. **Database updates**
   - Sets `Call.recording_url` to the `blob_url` (or to the original `audio_url` if the upload fails but a URL is still available).
   - Sets `Call.recording_duration` from `duration_seconds` (with validation).
   - Sets `Call.webhook_processed_at`, `Call.ended_at`, and `Call.duration_seconds` if they were not already populated.
   - Ensures `Call.status` is updated to `COMPLETED` if appropriate.

6. **Response**
   - After successful processing and database commit, logs an `elevenlabs_post_call_audio_processed` event and returns:

     ```json
     { "success": true }
     ```

#### `post_call_transcription` – Transcript and Summary Persistence

For `post_call_transcription` events, the backend expects a payload similar to:

```json
{
  "type": "post_call_transcription",
  "event_timestamp": 1734500000,
  "data": {
    "call_id": "conv_abc123",
    "transcript": "Full conversation text...",
    "summary": "Short summary of the conversation",
    "conversation_id": "conv_abc123",
    "has_audio": true,
    "has_user_audio": true,
    "has_response_audio": true
  }
}
```

Backend behavior:

1. Identifies the `Call` using the same `call_id`/`conversation_id` logic as above.
2. Performs recency and idempotency checks via `ElevenLabsEventLog`.
3. Extracts:
   - `transcript` – stored as `Call.transcript_text`.
   - `summary` – stored as `Call.transcript_summary`.
4. Attempts to derive a `caller_username` from the transcript using `_extract_username_from_transcript`, storing it on `Call.caller_username`.
5. Updates `Call.reception_status` to `"received"` when a transcript or answer is present, and sets `Call.reception_timestamp`, `Call.status`, and `Call.ended_at` if not already set.
6. Commits the updates and returns:

   ```json
   { "success": true }
   ```

### Error Handling, Logging, and Rate Limiting

The webhook endpoint includes robust error handling:

- **Signature errors**
  - Missing or invalid signatures result in `401` responses and are logged as `elevenlabs_webhook_missing_signature` or `elevenlabs_webhook_invalid_signature`.

- **Payload validation errors**
  - Non-JSON payloads, missing `type`, or missing `event_timestamp` are logged and produce early returns (with a safe JSON response) without attempting to persist any data.

- **Idempotency and duplicates**
  - Duplicate events (same `call_sid`, `event_type`, and `event_timestamp`) are detected via `ElevenLabsEventLog` and logged as `elevenlabs_webhook_duplicate_event` without re-processing.

- **Download and upload failures**
  - Audio download issues (HTTP errors or exceptions) and Azure Blob upload failures are logged with detailed context and abort the recording update for that event.

- **Rate limiting**
  - Basic per-client IP rate limiting is enforced to prevent abuse, returning HTTP 429 when a client exceeds the configured threshold.

### Testing Guidelines

To verify the ElevenLabs post-call webhook integration and recording persistence:

1. **Local environment**
   - Ensure `ELEVENLABS_WEBHOOK_SECRET`, `AZURE_STORAGE_CONNECTION_STRING`, and `AZURE_STORAGE_CONTAINER_NAME` are correctly set in `backend/.env`.
   - Run the backend:

     ```bash
     cd backend
     poetry run uvicorn app.main:app --reload
     ```

   - Expose the backend to the internet using a tunneling tool (for example, ngrok or Cloudflare Tunnel) and use the public URL in the ElevenLabs webhook configuration.

2. **Use ElevenLabs test webhooks**
   - From the ElevenLabs UI, send a **test `post_call_audio` webhook** and confirm:
     - The backend logs show the request as authenticated and processed.
     - A new blob appears in your Azure Storage container under the expected path.
     - The corresponding `Call` row has a non-null `recording_url` and `recording_duration`.
   - Send a **test `post_call_transcription` webhook** and verify:
     - `transcript_text` and `transcript_summary` are populated.
     - `caller_username`, `reception_status`, and `reception_timestamp` are set, if applicable.

3. **Run automated tests**
   - The backend includes tests (for example, `tests/test_elevenlabs_webhook.py`) that validate:
     - HMAC verification behavior.
     - Transcript persistence.
     - Audio webhook handling, including mocked download and Azure Blob upload.
   - Execute:

     ```bash
     cd backend
     poetry run pytest tests/test_elevenlabs_webhook.py
     ```

4. **End-to-end verification**
   - Place a real call through your ElevenLabs agent or Twilio integration.
   - After the call ends and ElevenLabs analysis completes:
     - Confirm that a new recording blob exists in Azure Storage.
     - Confirm that the Calls page in the frontend displays:
       - Updated call status.
       - Transcript summary.
       - A working “Play recording” link using the stored `recording_url`.

## 🔐 API Authentication

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password"}'

# Use token in header
curl http://localhost:8000/properties/ \
  -H "Authorization: Bearer <token>"
```

## 📊 User Roles

| Role | Permissions |
|------|-------------|
| Admin | Full access, user management |
| Manager | Lead assignment, team reports |
| Agent | Assigned leads, own calls |

## 🧪 Development

```bash
# Run backend tests
cd backend
poetry run pytest

# Run linting
poetry run ruff check .

# Generate migration
poetry run alembic revision --autogenerate -m "description"
```

## 🚢 Azure Deployment

1. Create Azure App Service
2. Configure environment variables
3. Set up CI/CD with GitHub Actions
4. Configure Twilio webhooks to Azure URL

## 📝 License

MIT License - ABC Real Estate
