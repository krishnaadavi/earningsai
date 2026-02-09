# Earnings AI Working Memory

Last updated: 2026-02-09

This file is the persistent session memory for ongoing work so progress survives chat resets or machine restarts.

## Current Objective

Continue the Earnings AI revamp with stable frontend UX, reliable backend ingestion/query paths, and clean deploy hygiene.

## What Was Already Done (Recent)

- Added query routing for:
  - weekly earnings and "today" summaries
  - generic questions without mandatory `doc_id`
  - highlights/calendar/movers flows
- Added API-first summaries integration with providers (Finnhub + Alpha Vantage).
- Added dashboard UX improvements:
  - chat quick actions
  - top summaries panel
- Added ingestion metrics/admin endpoints and instrumentation.

## Changes Done In This Session

- Fixed React hook dependency warning in `frontend/app/dashboard/page.tsx` by including `refreshSummaries` in the `useEffect` dependency list.
- Frontend lint now passes with no warnings/errors.
- Verified `frontend/.vercelignore` exists and currently contains:
  - `.env.local`
  - `.next`
- Detected that `frontend/.next` build artifacts are tracked in git (96 tracked files), causing noisy worktree status.
- Untracked `frontend/.next` from git index via `git rm -r --cached frontend/.next` (files remain ignored locally by `.gitignore`).
- Created root persistence docs:
  - `memory.md` (session continuity log)
  - `plan.md` (live roadmap and status)
- Set up backend virtualenv and ran tests:
  - `7 passed, 2 skipped` (warnings only; no failures)
- Fixed trade ideas drawer action in `frontend/app/dashboard/page.tsx`:
  - `Open detail` now opens `DetailDrawer` and clears stale company/summary context.
- Re-ran frontend lint after the drawer fix; still clean.

## Important Current Git State

- The `.next` cleanup appears as staged deletions of previously tracked generated files (expected from untracking step).
- Other meaningful pending files:
  - `frontend/app/dashboard/page.tsx`
  - `frontend/.vercelignore`
  - `memory.md`
  - `plan.md`

## Known Environment Notes

- Backend tests not yet run in current shell environment because `pytest` is not installed (`No module named pytest`).
- Existing dirty tree included tracked build artifacts under `frontend/.next` and one untracked file `frontend/.vercelignore`.

## Pending / Next

1. Install backend test dependencies in a local virtualenv and run test suite.
2. Continue revamp implementation tasks from `plan.md`.
3. Keep `memory.md` and `plan.md` updated after each meaningful change.
4. Decide commit slicing strategy:
   - repo hygiene (`.next` untracking)
   - frontend dashboard fixes
   - continuity docs

## Working Rules For Future Sessions

- Update this file at the end of each meaningful change set:
  - what changed
  - why
  - what is next
- Keep entries concise and chronological so context is quick to recover.
