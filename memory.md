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
- Committed changes in three slices:
  - `dd29a61` chore(frontend): stop tracking Next.js build artifacts
  - `b17bc57` fix(dashboard): stabilize summaries refresh and trade-idea detail drawer
  - `c349ed5` docs: add persistent memory and revamp planning files
- Added GitHub remote:
  - `origin` => `https://github.com/krishnaadavi/earningsai.git`
- Push to GitHub `main` was initially blocked by legacy oversized file history (`frontend/node_modules/...next-swc...node`).
- Published a clean snapshot to GitHub by creating/pushing an orphan branch without legacy blobs:
  - `publish-main-clean` -> `origin/main` (`792abd2`)
- Added follow-up docs commit onto GitHub main:
  - `a541565` docs: update memory and plan after GitHub publish setup
- Realigned local `main` to `origin/main` so future pushes are straightforward.
- Created safety backup before alignment:
  - `backup/main-pre-align-20260209` (points to pre-align local history)
- Linked local `frontend` directory to Vercel project `earnings-ai-frontend`.
- Deployed production frontend via Vercel CLI:
  - deployment id: `dpl_H6BCYWCSMM1A44o4oRLYWu2DAyQ3`
  - production URL: `https://earnings-ai-frontend-o3wxn8u5y-krishnaadavi-gmailcoms-projects.vercel.app`
  - aliased to `https://tradeearnings.ai` and `https://www.tradeearnings.ai`
- Verified backend health endpoint returns `{"status":"ok"}` at `https://earnings-ai-backend-057a34debf24.herokuapp.com/health`.
- Added a visible dashboard marker (`Revamp build: 2026-02-09`) in `frontend/app/dashboard/page.tsx` to make deploy verification explicit.
- Redeployed frontend to production:
  - deployment id: `dpl_BNQ14dmLMyA1BLyGVonuqZa9heJo`
  - URL: `https://earnings-ai-frontend-76vv5vcng-krishnaadavi-gmailcoms-projects.vercel.app`
- Verified marker is present in live HTML at `https://tradeearnings.ai/dashboard`.
- Implemented a stronger visual redesign pass across dashboard surfaces:
  - refreshed shell/background in `frontend/app/globals.css`
  - redesigned `Sidebar` to a rounded card layout with stronger hierarchy
  - modernized `TickerChip` and `HighlightCard` visuals
  - upgraded dashboard hero/title and section presentation in `frontend/app/dashboard/page.tsx`
- Redeployed redesigned frontend to production:
  - deployment id: `dpl_Hhi4YzJSrVysGwAXY542JJUy52MP`
  - URL: `https://earnings-ai-frontend-7m9z518zt-krishnaadavi-gmailcoms-projects.vercel.app`
  - alias confirmed: `https://tradeearnings.ai`
- Applied a second-pass design polish focused on visual quality:
  - removed hardcoded light gradients that looked broken in dark mode
  - improved sidebar shell theming and hierarchy labels
  - refined chat panel surface/background contrast in dark mode
  - tightened dashboard title/metadata treatment and section surface consistency
- Redeployed polished UI to production:
  - deployment id: `dpl_XPVvnCnj6MoBwoaneSdpLf9mVkDC`
  - URL: `https://earnings-ai-frontend-j337sca51-krishnaadavi-gmailcoms-projects.vercel.app`
  - alias confirmed: `https://tradeearnings.ai`

## Important Current Git State

- Local `main` now tracks `origin/main` at `a541565`.
- `origin/main` contains the clean published history suitable for GitHub pushes.
- Pre-alignment local history is preserved on `backup/main-pre-align-20260209`.

## Known Environment Notes

- Backend tests pass in local virtualenv: `7 passed, 2 skipped`.
- Frontend lint passes with no warnings/errors.
- Vercel CLI account: `krishnaadavi-3536` (project scope `krishnaadavi-gmailcoms-projects`).

## Pending / Next

1. Continue revamp implementation tasks from `plan.md`.
2. Keep `memory.md` and `plan.md` updated after each meaningful change.
3. If UI appears stale in browser, hard refresh or clear cache against latest deployment `dpl_H6BCYWCSMM1A44o4oRLYWu2DAyQ3`.
4. Remove temporary visible build marker once user confirms updated interface is seen.
5. Continue with deeper component-level redesign (ChatPanel/DetailDrawer) if current visual refresh is still not sufficient.
6. If accepted, remove temporary deploy-verification marker language and finalize visual system tokens.

## Working Rules For Future Sessions

- Update this file at the end of each meaningful change set:
  - what changed
  - why
  - what is next
- Keep entries concise and chronological so context is quick to recover.
