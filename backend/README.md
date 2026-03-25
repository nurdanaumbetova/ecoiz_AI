# EcoIZ Backend

Production-like backend for the Xcode SwiftUI client:

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic

The API contract matches the current iOS client.

## Local setup

1. Start PostgreSQL:

```bash
cd /Users/akerkeamirtay/Desktop/dipl/EcoIZ.02/backend
docker compose up -d
```

2. Create virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

3. Copy env:

```bash
cp .env.example .env
```

4. Run migrations:

```bash
alembic upgrade head
```

5. Start API:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## AI chat

Chat endpoint:

```bash
POST /chat/messages
```

The backend now builds a personalized AI context from:

- user points
- streakDays
- co2SavedTotal
- latest activities
- user challenges
- latest posts
- recent chat history

OpenAI settings are read from `.env`:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_TIMEOUT_SECONDS`
- `OPENAI_TEMPERATURE`
- `OPENAI_MAX_TOKENS`

If `OPENAI_API_KEY` is empty, the backend falls back to local rule-based replies.

## iOS client

The SwiftUI app is configured to use this backend at `http://127.0.0.1:8000`.
