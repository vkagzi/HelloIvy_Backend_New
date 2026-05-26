# HelloIvy API

AI-powered career and academic Stream & Subject Selection platform. Students complete guided voice/text sessions that produce personalised career recommendations and academic domain reports.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
  - [1. Start Infrastructure](#1-start-infrastructure)
  - [2. Python Environment](#2-python-environment)
  - [3. Environment Variables](#3-environment-variables)
  - [4. Database Migration](#4-database-migration)
  - [5. Run the Server](#5-run-the-server)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [WebSocket Endpoints](#websocket-endpoints)
- [Environment Variables Reference](#environment-variables-reference)
- [Production Deployment](#production-deployment)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.12 |
| **Framework** | Django 6.0 + Django REST Framework 3.16 |
| **ASGI Server (dev)** | Daphne 4.2 |
| **ASGI Server (prod)** | Gunicorn 23 + UvicornWorker |
| **WebSockets** | Django Channels 4.3 + channels_redis 4.3 |
| **Database** | PostgreSQL 17 (`psycopg[binary]` 3.2) |
| **Cache / Channel Layer** | In-memory (dev) / Redis (prod) |
| **LLM Orchestration** | LangChain 1.2 + langchain-openai + langchain-google-genai |
| **LLM Providers** | Azure OpenAI (primary), OpenAI (fallback), Google Gemini (RAG) |
| **Speech-to-Text** | Deepgram SDK 4.8 / OpenAI Whisper |
| **Text-to-Speech** | Azure OpenAI TTS (`gpt-4o-mini-tts`) |
| **Embeddings / Vector Search** | sentence-transformers 5.1 + FAISS-cpu 1.9 |
| **Auth** | Custom stateless JWT (PyJWT 2.10, `HS256`, 365-day expiry) |
| **Email** | SendGrid 6.12 |
| **API Docs** | drf-spectacular 0.28 (Swagger UI + Redoc) |
| **Static Files** | WhiteNoise 6.8 |

---

## Prerequisites

- **Docker & Docker Compose** — for PostgreSQL and pgAdmin
- **Python 3.12** — runtime version (see `runtime.txt`)
- Accounts / API keys for: Azure OpenAI, SendGrid (required); OpenAI, Deepgram, Google Gemini (optional)

---

## Local Development Setup

### 1. Start Infrastructure

```bash
docker compose up -d postgres pgadmin
```

| Service | URL | Credentials |
|---------|-----|-------------|
| PostgreSQL | `localhost:12322` | `admin` / `admin123` |
| pgAdmin | http://localhost:12323 | configured via `PGADMIN_*` env in docker-compose |

### 2. Python Environment

```bash
python3.12 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in every value marked **required**. See [Environment Variables Reference](#environment-variables-reference) for details.

### 4. Database Migration

```bash
python manage.py migrate
```

Optionally seed location data (countries / states / cities):

```bash
python manage.py seed_locations   # loads cities.csv
```

### 5. Run the Server

**HTTP only (no WebSocket support):**

```bash
python manage.py runserver
```

**Full ASGI — required for WebSocket voice sessions:**

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

**API docs** are available at:
- Swagger UI: http://localhost:8000/api/schema/swagger-ui/
- Redoc: http://localhost:8000/api/schema/redoc/
- Raw schema: http://localhost:8000/api/schema/

---

## Project Structure

```
helloivy-api/
├── config/               # Django project config (settings, URLs, ASGI/WSGI)
│   └── settings/         # Base, dev, and prod settings split
├── apps/
│   ├── accounts/         # User model, JWT auth, OTP email verification
│   ├── profiles/         # User profile JSON storage
│   └── locations/        # Static countries / states / cities geodata
├── career_discovery/     # AI career counselling sessions (20 questions → 8 career recs)
├── domain_discovery/     # AI academic Stream & Subject Selection (25 questions → Top 3 domains + PDF report)
├── utils/                # Shared helpers: Azure OpenAI, JWT, email, TTS, realtime consumers
├── conv_rag/             # Conversational RAG system (essay guidance)
├── docs/                 # Feature documentation and prompting guides
├── audio-recordings/     # Offline transcription and analysis scripts
├── resumes/              # Resume file storage
├── requirements.txt      # Python dependencies
├── docker-compose.yml    # Local dev infra (Postgres, pgAdmin, API)
├── Dockerfile            # Dev container image
├── Dockerfile.prod       # Production container image
├── gunicorn.conf.py      # Gunicorn ASGI config (prod)
├── start.sh              # Production startup script
├── manage.py
└── .env.example          # Template for environment variables
```

---

## API Endpoints

All REST endpoints are prefixed with `/api/`.

| Prefix | Purpose |
|--------|---------|
| `GET /` | Health check |
| `/api/accounts/` | Auth — signup, verify, login, password reset, user settings |
| `/api/profiles/` | User profile read / update |
| `/api/locations/` | Countries, states, cities lookup |
| `/api/tts/` | Azure TTS speech generation |
| `/api/career-discovery/` | Career session CRUD, messages, recommendations |
| `/api/domain-discovery/` | Domain session CRUD, report generation/download, transcript, audio |

### Accounts

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/accounts/signup/` | Register with email, send OTP |
| POST | `/api/accounts/verify/` | Verify email OTP |
| POST | `/api/accounts/login/` | Login, returns JWT |
| POST | `/api/accounts/password-reset/request/` | Request password reset OTP |
| POST | `/api/accounts/password-reset/confirm/` | Confirm OTP, set new password |
| POST | `/api/accounts/accept-terms/` | Accept terms & conditions |
| GET | `/api/accounts/me/` | Get current user |
| PATCH | `/api/accounts/settings/` | Update account settings |

### Career & Degree Selection 

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/career-discovery/` | Create new session |
| GET | `/api/career-discovery/list/` | List user's sessions |
| GET | `/api/career-discovery/<id>/` | Get session detail |
| POST | `/api/career-discovery/<id>/end/` | End session |
| POST | `/api/career-discovery/<id>/pause/` | Pause session |
| GET | `/api/career-discovery/<id>/messages/` | Get messages |
| GET | `/api/career-discovery/<id>/messages/history/` | Get message history |
| POST | `/api/career-discovery/<id>/recommendations/generate/` | Generate career recommendations |
| GET | `/api/career-discovery/<id>/recommendations/` | Fetch recommendations |

### Stream & Subject Selection

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/domain-discovery/` | Create new session |
| GET | `/api/domain-discovery/list/` | List user's sessions |
| GET | `/api/domain-discovery/<id>/` | Get session detail |
| POST | `/api/domain-discovery/<id>/end/` | End session |
| GET | `/api/domain-discovery/<id>/report/` | Get domain report |
| GET | `/api/domain-discovery/<id>/report/download/` | Download PDF report |
| GET | `/api/domain-discovery/<id>/results/` | Get RIASEC results |
| GET | `/api/domain-discovery/<id>/transcript/` | Get session transcript |
| GET | `/api/domain-discovery/<id>/transcript/download/` | Download transcript |
| POST | `/api/domain-discovery/audio/transcribe/` | Transcribe audio file |
| POST | `/api/domain-discovery/audio/speech/` | Generate speech |

---

## WebSocket Endpoints

Connect using `ws://` (dev) or `wss://` (prod).

| Path | Description |
|------|-------------|
| `ws/voice/realtime/?feature=<feature>&session_id=<id>` | **Unified realtime voice endpoint.** Feature is dispatched based on the `feature` query param (`career_discovery`, `domain_discovery`). |
| `ws/career-discovery/realtime/` | Legacy Career & Degree Selection voice session (backward compat) |
| `ws/domain-discovery/realtime/` | Legacy Stream & Subject Selection voice session (backward compat) |

All realtime consumers relay audio to the **Azure OpenAI Realtime API** over a WebSocket-to-WebSocket proxy.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ | — | Django secret key; also used as JWT signing key |
| `DEBUG` | ✅ | `True` | Set to `False` in production |
| `ALLOWED_HOSTS` | ✅ prod | `*` | Comma-separated list of allowed hostnames |
| **Database** | | | |
| `DATABASE_URL` | ✅ | — | Full Postgres DSN e.g. `postgres://user:pass@host:5432/db` |
| `DB_CONN_MAX_AGE` | — | `600` | Persistent DB connection lifetime (seconds) |
| **Azure OpenAI (Chat)** | | | |
| `AZURE_OPENAI_ENDPOINT` | ✅ | — | Azure OpenAI resource endpoint URL |
| `AZURE_OPENAI_API_KEY` | ✅ | — | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | ✅ | — | Chat model deployment name (e.g. `gpt-5.2`) |
| **Azure OpenAI (TTS)** | | | |
| `AZURE_OPENAI_TTS_API_KEY` | — | `AZURE_OPENAI_API_KEY` | TTS-specific key; falls back to main key |
| `AZURE_OPENAI_TTS_ENDPOINT` | — | `AZURE_OPENAI_ENDPOINT` | TTS-specific endpoint; falls back to main endpoint |
| `AZURE_OPENAI_TTS_DEPLOYMENT` | — | `gpt-4o-mini-tts` | TTS model deployment name |
| **Azure OpenAI (Realtime Voice)** | | | |
| `AZURE_OPENAI_REALTIME_DEPLOYMENT` | — | `gpt-realtime-1.5` | Realtime voice model deployment name |
| `AZURE_OPENAI_REALTIME_API_VERSION` | — | `2024-10-01-preview` | Realtime API version |
| **Email** | | | |
| `SENDGRID_API_KEY` | ✅ | — | SendGrid API key for OTP emails |
| `SENDGRID_FROM_EMAIL` | ✅ | — | Verified SendGrid sender address |
| **Optional Services** | | | |
| `GEMINI_API_KEY` | — | — | Google Gemini API key for RAG system |
| `DEEPGRAM_API_KEY` | — | — | Deepgram API key for speech-to-text |
| **CORS** | | | |
| `CORS_ALLOW_ALL_ORIGINS` | — | `True` | Set to `False` in production |
| `CORS_ALLOWED_ORIGINS` | — | — | Comma-separated allowed origins (when above is `False`) |
| **Production / Security** | | | |
| `REDIS_URL` | — prod | — | Redis URL for production channel layer (e.g. `redis://localhost:6379`) |
| `SECURE_SSL_REDIRECT` | — prod | `False` | Force HTTPS |
| `SESSION_COOKIE_SECURE` | — prod | `False` | Secure session cookies |
| `CSRF_COOKIE_SECURE` | — prod | `False` | Secure CSRF cookies |
| `ENABLE_HSTS` | — prod | `False` | Enable HSTS headers |
| `LOG_FILE_PATH` | — | — | Path for error log file |
| `DJANGO_LOG_LEVEL` | — | `INFO` | Django logging level |

---

## Production Deployment

### Docker

```bash
docker build -f Dockerfile.prod -t helloivy-api .
docker run -p 8000:8000 --env-file .env helloivy-api
```

### Gunicorn (ASGI)

The `gunicorn.conf.py` uses a custom `UvicornWorkerNoLifespan` to serve the ASGI application:

```bash
gunicorn config.asgi:application -c gunicorn.conf.py
```

Or use the provided startup script:

```bash
./start.sh
```

### Key production checklist

- Set `DEBUG=False`
- Set `ALLOWED_HOSTS` to your domain
- Set `CORS_ALLOW_ALL_ORIGINS=False` and configure `CORS_ALLOWED_ORIGINS`
- Enable `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `ENABLE_HSTS`
- Provide `REDIS_URL` so Django Channels uses a persistent channel layer
- Run `python manage.py collectstatic` before starting (handled by `start.sh`)

### Cloud Build

A `cloudbuild.yaml` is included for Google Cloud Build CI/CD pipelines. A `vercel.json` / `build_vercel.sh` are included for Vercel deployments.
