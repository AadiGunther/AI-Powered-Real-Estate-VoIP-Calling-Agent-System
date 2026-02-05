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
