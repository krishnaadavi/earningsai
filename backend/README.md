# Earnings AI Backend (Phase 0)

FastAPI backend to upload a single PDF (10-Q/10-K/transcript), parse to chunks with page spans, embed, retrieve, and answer questions with citations. Heroku-ready.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Env
Create `.env` from `.env.example` and set `OPENAI_API_KEY` (optional; without it, a deterministic fallback embedding is used and answers are basic).

## Endpoints
- `GET /health` → status
- `POST /api/upload` (multipart/form-data, field `file`) → `{ doc_id, chunk_count }`
- `POST /api/query` `{ doc_id, question }` → bullets with citations and simple chart

## Heroku
- `runtime.txt` (Python 3.11)
- `Procfile` (uvicorn)
- `requirements.txt`

Deploy:
```bash
heroku create earnings-ai-backend
heroku config:set OPENAI_API_KEY=... ALLOW_ORIGINS="http://localhost:3000,https://*.vercel.app" -a earnings-ai-backend
git init && git add . && git commit -m "init backend"
heroku git:remote -a earnings-ai-backend
git push heroku main
```

## Notes
- Phase 0 keeps an in-memory store. Restarting the dyno clears documents.
- Token/cost guard: kept minimal; model usage is limited by small contexts and you can add caps via env.
