# Earnings AI – Research Assistant (Phase 0)

Upload a single earnings PDF (10-Q/10-K/transcript), ask natural questions, and get concise answers with citations and a simple trend chart.

- Backend: FastAPI (Python 3.11), Heroku-ready
- Frontend: Next.js 14 (App Router), Vercel-ready

## Local Run
### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY if available
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Visit http://localhost:3000. Set `NEXT_PUBLIC_API_BASE_URL` in `.env.local` if your backend is not on 8000.

## API
- `GET /health`
- `POST /api/upload` (multipart: `file`) → `{ doc_id, chunk_count }`
- `POST /api/query` `{ doc_id, question }` → `{ bullets: [{text, citations:[{section,page,snippet}]}], chart:{labels,values} }`

## Deployment
### Backend (Heroku)
```bash
cd backend
heroku create earnings-ai-backend
heroku buildpacks:set heroku/python -a earnings-ai-backend
heroku config:set OPENAI_API_KEY=... ALLOW_ORIGINS="https://*.vercel.app" -a earnings-ai-backend
git init && git add . && git commit -m "init backend"
heroku git:remote -a earnings-ai-backend
git push heroku main
```

### Frontend (Vercel)
- Import the repo
- Env: `NEXT_PUBLIC_API_BASE_URL=https://earnings-ai-backend.herokuapp.com/api`

## Notes
- Phase 0 uses an in-memory store; restarting the backend clears uploaded docs.
- Query cap enforced via `BUDGET_MAX_QUERIES`.
- Without `OPENAI_API_KEY`, the app uses deterministic fallback embeddings and minimal answers; citations still included.
