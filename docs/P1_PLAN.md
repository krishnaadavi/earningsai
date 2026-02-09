# Earnings AI – Phase 1 (P1) Plan: Comprehensive Financial Analytics Backend

This plan builds on Phase 0 (single-PDF, in‑memory RAG) to deliver a production‑oriented backend that extracts, stores, and serves financial analytics with citations.

## P1 Goals
- Persist uploaded docs and analysis results (multi-doc support).
- Robust PDF ingestion with text + tables, section/page spans.
- Deterministic metric extraction for core KPIs with citations.
- Forward‑looking guidance + buyback/dividend detection.
- Time‑series metrics and computed analytics (YoY/QoQ, margins, trends).
- RAG router: metric store first, LLM fallback with citations.

## Architecture
- API: FastAPI (existing).
- DB: Postgres + pgvector (preferred) or Qdrant. Managed option: Neon Postgres (free tier) or Heroku Postgres with pgvector.
- Queue/worker: RQ (Redis) or simple background job; Heroku worker dyno for ingestion if needed.
- Embeddings: OpenAI text-embedding-3-small (1536 dims). Stored in `pgvector`.
- Storage model: documents → pages → chunks (vectorized) + metrics derived.

### Services/Modules
- `ingest`: PDF → pages (text + tables) → sections → chunks → embeddings → DB.
- `extractors`: deterministic parsers for metrics and events with source citations.
- `series`: time-series builder for metrics across a document.
- `qa_router`: answers first from metrics store; falls back to RAG.

## Persistence Schema (draft)
- `documents` (id, created_at, filename, company, form_type, fiscal_year, fiscal_period, source_url, ingest_status, error)
- `pages` (id, doc_id, page_number, text, blocks_json)
- `chunks` (id, doc_id, section, page_start, page_end, text, embedding vector(1536))
- `metrics` (id, doc_id, metric_name, period_label, period_start, period_end, value, unit, is_guidance bool, range_low, range_high, confidence, source_chunk_id, source_page_start, source_page_end, source_snippet)
- `events` (id, doc_id, event_type [buyback, dividend], details_json, confidence, source_* fields like above)
- Indexes: `metrics(doc_id, metric_name, period_label)`, `chunks USING ivfflat (embedding vector_cosine_ops)`

## Ingestion Pipeline
- PDF parsing: PyMuPDF for text/blocks + pdfplumber for table rows (fallback: heuristic grid from PyMuPDF blocks when tables fail).
- Section detection: improved headers + TOC heuristics; keep page spans.
- Chunking: paragraph-aware, table-aware; store `section`, `page_start/end`.
- Embedding: OpenAI; store in `pgvector`.
- Extraction passes (deterministic first):
  - Core metrics: Revenue, Cost, Gross Profit, Gross Margin, OpEx, Operating Income, Operating Margin, Net Income, EPS (GAAP/Non‑GAAP), CFO, CAPEX, FCF, FCF margin.
  - Guidance: revenue/EPS/margins for next quarter/year; capture ranges.
  - Corporate actions: buybacks/dividends (amount, authorization size, period).
- Each extracted datum stores citation pointers (chunk/page/snippet) + confidence.

## APIs (draft)
- `POST /api/ingest` → `{ doc_id }` (async status optional)
- `GET /api/docs/:doc_id` → metadata + status
- `GET /api/metrics` (query: `doc_id`, `metric`, `period`) → value + citation(s)
- `GET /api/series` (query: `doc_id`, `metric`) → `{ labels, values, citations }`
- `GET /api/guidance` (query: `doc_id`, optional `metric`) → structured guidance + citations
- `GET /api/buybacks` (query: `doc_id`) → detected events + citations
- `POST /api/query` → routes to metrics first; falls back to RAG with citations

## Frontend additions (minimal)
- After upload, show detected company/form/period.
- Tabs: Answers (existing), Metrics (table of core KPIs), Trends (chart from `/series`).
- Each metric row: info icon to show source citation(s).

## Milestones & Acceptance
1) Persistence & ingestion (DB, embeddings, chunk store)
- Able to upload ≥3 docs; data survives restarts.
- Vector search working via pgvector.

2) Core metric extractors
- Return ≥10 KPIs per doc with citations.
- Numeric unit normalization (K/M/B) and margins.

3) Guidance + buybacks
- Extract structured guidance with ranges where present.
- Detect buyback announcements with amounts and dates.

4) APIs & UI surfacing
- `/metrics`, `/series`, `/guidance`, `/buybacks` live.
- UI shows metrics + citations; charts render from `/series`.

5) Evaluation (E2E)
- Test on 5 filings/transcripts; ≥80% extraction accuracy on core metrics; all answers cited or “Insufficient context.”
- Latency targets: ingest <60s/file on Hobby; query <4s typical.

## Tooling
- ORM/migrations: SQLAlchemy + Alembic.
- Background jobs: RQ with Redis (Heroku Redis mini) or synchronous for MVP.
- Observability: structured logs; optional Sentry.

## Env & Ops
- `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `EMBEDDING_MODEL`, cost caps.
- Heroku: add Postgres + Redis add‑ons; one web dyno + optional worker dyno.
- Replace `runtime.txt` with `.python-version` ("3.11").

## Risks & Mitigations
- Table parsing accuracy: combine pdfplumber + heuristics; optionally fall back to LLM‑assisted parsing for hard cases with budget guard.
- Guidance is often in transcripts/PRs: advise users to upload those for forward‑looking Qs.
- Cost/latency: embed once on ingest; tighten prompt sizes; cache metric queries.

## Timeline (indicative)
- Week 1: DB + pgvector, ingestion, chunk store, `/ingest` + `/metrics` (subset)
- Week 2: Full core extractors, `/series`, `/guidance`, `/buybacks`, UI surfacing, E2E tests

## Next Steps
- Choose persistence: Neon Postgres (pgvector) or Heroku Postgres (pgvector). Recommend Neon (free tier, simple pgvector).
- I’ll scaffold SQLAlchemy models, Alembic, and DB connection, then add `/ingest` + `/metrics` endpoints.
