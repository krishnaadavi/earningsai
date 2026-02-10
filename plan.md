# Earnings AI Revamp Plan

Last updated: 2026-02-09

## Goals

- Deliver a useful earnings workflow end-to-end:
  - discover upcoming events
  - ingest relevant docs
  - query insights quickly in chat
- Keep deploy/runtime hygiene clean for Heroku backend + Vercel frontend.
- Reduce dev friction from generated artifact churn.

## Active Workstreams

1. Frontend dashboard quality
   - [x] Add summaries panel and chat quick actions
   - [x] Fix dashboard hook lint warning
   - [x] Validate "Open detail" behavior for generated trade ideas
   - [x] Ensure frontend lint is clean after dashboard updates
   - [ ] Remove temporary deploy-verification build badge after confirmation
2. Data freshness and ingestion UX
   - [x] Add refresh + ingest admin actions in dashboard
   - [ ] Improve user-facing status/error messaging for ingestion failures
3. Repo hygiene and release readiness
   - [x] Stop tracking `frontend/.next` artifacts in git index
   - [x] Commit `.next` index cleanup so local builds stay quiet going forward
   - [x] Run backend tests in a prepared Python env
   - [x] Publish repository to GitHub (`krishnaadavi/earningsai`)
   - [x] Align local `main` with `origin/main` after clean GitHub publish
   - [x] Trigger production Vercel deploy for current frontend state
4. Documentation continuity
   - [x] Create persistent `memory.md`
   - [x] Create persistent `plan.md`
   - [ ] Keep both files updated after each plan or implementation change

## Plan Decisions

- Use `plan.md` as source of truth for roadmap/task status.
- Use `memory.md` as session continuity log (what happened and what is next).
- Prefer incremental, testable changes and keep lint clean before moving to next task.
- Temporary publish decision: use a clean GitHub root snapshot because legacy history contains oversized files blocked by GitHub.
- Local `main` is now normalized to track `origin/main`; old pre-alignment history is retained on a backup branch.
- Deploy frontend directly from `frontend/` via Vercel CLI when we need an immediate production refresh.

## Immediate Next Actions

1. Continue frontend/backend revamp items and update this plan as scope evolves.
2. Optionally address backend deprecation warnings (`FastAPI on_event`, `pydantic dict`, httpx app shortcut) in a dedicated technical-debt pass.
