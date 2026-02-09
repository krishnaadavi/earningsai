# Earnings AI Frontend (Phase 0)

Minimal Next.js app to upload a single PDF and ask questions, rendering bullets with citations and a simple line chart.

## Run locally
```bash
cp .env.example .env.local
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` to your backend, e.g. `http://127.0.0.1:8000/api` or your Heroku URL like `https://earnings-ai-backend.herokuapp.com/api`.

## Deploy (Vercel)
- Import repo in Vercel
- Add env `NEXT_PUBLIC_API_BASE_URL` pointing to your Heroku backend `/api`
