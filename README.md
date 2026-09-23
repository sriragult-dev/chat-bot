# DataMentor API

A small FastAPI service wrapping the Google Gemini API. It exposes a chat bot with a
fixed persona: it answers **data science** questions and gives **practical guidance to
startups**. Questions outside that scope get a short, friendly redirect.

Includes streaming responses, per-session conversation memory, auto-generated Swagger
docs, and a minimal browser chat page.

## Setup

1. Put your Gemini API key in `.env` (copy `.env.example` if you don't have one):

   ```
   GEMINI_API_KEY=AIza...
   ```

   Get a key at <https://aistudio.google.com/apikey>. Real AI Studio keys start with
   `AIza`. `.env` is gitignored.

2. Install dependencies into the project venv:

   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

## Run

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- Chat UI: <http://127.0.0.1:8000/>
- Swagger docs: <http://127.0.0.1:8000/docs>

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Browser chat UI |
| `GET` | `/health` | Status, active model, live session count |
| `POST` | `/chat` | `{session_id?, message}` → `{session_id, reply}` |
| `POST` | `/chat/stream` | Same body, streamed as server-sent events |
| `GET` | `/history/{session_id}` | What the bot currently remembers |
| `DELETE` | `/session/{session_id}` | Clear that session's memory |

`session_id` is optional. Omit it on the first message and the server returns a new
one; send it back on later messages to keep context.

### Example

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d '{\"message\":\"How do I pick a baseline model for churn prediction?\"}'
```

## Configuration

All settings live in `.env`:

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Your AI Studio key |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Model to call |
| `MAX_HISTORY_TURNS` | `10` | Exchanges kept per session |
| `SESSION_TTL_MINUTES` | `60` | Idle time before a session is dropped |
| `PORT` | `8000` | Port hint for the server |

## Notes

- Conversation memory is **in-process**: it is lost on restart and is not shared across
  workers. Swap `app/memory.py` for Redis if you need it to survive either.
- CORS is wide open (`*`) because this is a local dev project. Lock it down before
  deploying anywhere public.
- The bot's persona and scope guardrail live in one place: `app/prompts.py`. Edit that
  constant to change what it will and won't discuss.
