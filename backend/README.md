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

The AI is configured to answer broader user questions too, not only narrow eco prompts. With `OPENAI_API_KEY` enabled, the chat behaves much closer to a general assistant and uses the user context as personalization, not as a rigid template.

OpenAI settings are read from `.env`:

- `AI_PROVIDER` (`openrouter` by default, or `openai`)
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `AI_TIMEOUT_SECONDS`
- `AI_TEMPERATURE`
- `AI_MAX_TOKENS`
- `AI_HISTORY_LIMIT`

Important: if the selected provider key is empty, the backend falls back to local rule-based replies, so the chat will still feel more limited and more template-like than a real model response.

## iOS client

The SwiftUI app is configured to use this backend at `http://127.0.0.1:8000`.
