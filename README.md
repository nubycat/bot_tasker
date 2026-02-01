# TELEGRAM_BOT_TASKER
Stage 1 — in progress

Telegram task bot + backend.

---

## Project structure
- `backend/` — FastAPI backend (SQLAlchemy / Alembic / Postgres)
- `bot/` — Telegram bot (aiogram)
- `.env.example` — environment variables example
- `docker-compose.yml` — WIP

---

## Environment variables

Create `.env` from `.env.example` and fill required values.

- `BOT_TOKEN` — Telegram bot token (used by bot)
- `BACKEND_URL` — backend base URL  
  example: `http://127.0.0.1:8000`
- `DATABASE_URL` — PostgreSQL DSN (used by backend)

⚠️ Never commit `.env` with real tokens.

---

## How to run (local)

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
