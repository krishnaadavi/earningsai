from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import and_

from app.db.base import db_session
from app.db.models import Document, EarningsEvent, Watchlist
from app.db.persistence import is_db_enabled

router = APIRouter()


class DashboardEventOut(BaseModel):
    id: str
    ticker: str
    company: Optional[str] = None
    event_date: str
    time_of_day: Optional[str] = None
    status: Optional[str] = None


class ReportLinkOut(BaseModel):
    ticker: str
    company: Optional[str] = None
    doc_id: str
    source_url: str
    form_type: Optional[str] = None
    created_at: Optional[str] = None
    title: str
    is_new: bool = False


class RiskRowOut(BaseModel):
    ticker: str
    company: Optional[str] = None
    eta: str
    time_of_day: Optional[str] = None
    risk: str


class AlertItemOut(BaseModel):
    severity: str
    title: str
    detail: str


class DashboardOverviewOut(BaseModel):
    as_of: str
    today: List[DashboardEventOut]
    upcoming: List[DashboardEventOut]
    reported: List[DashboardEventOut]
    report_links: List[ReportLinkOut]
    watchlist_risk: List[RiskRowOut]
    alert_timeline: List[AlertItemOut]
    counts: dict


def _event_to_out(ev: EarningsEvent) -> DashboardEventOut:
    return DashboardEventOut(
        id=ev.id,
        ticker=ev.ticker,
        company=ev.company,
        event_date=(ev.event_date.isoformat() if ev.event_date else ""),
        time_of_day=ev.time_of_day,
        status=ev.status,
    )


def _to_utc_dt_from_ms(ms: Optional[int]) -> Optional[datetime]:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except Exception:
        return None


@router.get("/dashboard/overview", response_model=DashboardOverviewOut)
async def dashboard_overview(
    limit: int = Query(default=8, ge=1, le=50),
    since_ts: Optional[int] = Query(default=None, description="Epoch milliseconds for new report detection"),
) -> DashboardOverviewOut:
    now = datetime.now(timezone.utc)
    today_d = now.date()

    if not is_db_enabled():
        sample_today = [
            DashboardEventOut(
                id="sample-1",
                ticker="AAPL",
                company="Apple Inc.",
                event_date=today_d.isoformat(),
                time_of_day="BMO",
                status="reported",
            )
        ]
        return DashboardOverviewOut(
            as_of=now.isoformat(),
            today=sample_today,
            upcoming=[],
            reported=sample_today,
            report_links=[],
            watchlist_risk=[],
            alert_timeline=[
                AlertItemOut(
                    severity="low",
                    title="DB not enabled",
                    detail="Running in fallback mode; connect DATABASE_URL for full live data.",
                )
            ],
            counts={
                "today": len(sample_today),
                "upcoming": 0,
                "reported": len(sample_today),
                "report_links": 0,
                "watchlist_risk": 0,
            },
        )

    since_dt = _to_utc_dt_from_ms(since_ts)

    with db_session() as s:
        range_start = today_d - timedelta(days=7)
        range_end = today_d + timedelta(days=14)
        rows: List[EarningsEvent] = (
            s.query(EarningsEvent)
            .filter(and_(EarningsEvent.event_date >= range_start, EarningsEvent.event_date <= range_end))
            .order_by(EarningsEvent.event_date.asc(), EarningsEvent.ticker.asc())
            .all()
        )

        today_rows = [r for r in rows if r.event_date == today_d][:limit]
        upcoming_rows = [r for r in rows if r.event_date > today_d][:limit]
        reported_rows = [
            r for r in rows if (r.status or "").lower() == "reported" or (r.event_date and r.event_date < today_d)
        ]
        reported_rows = sorted(reported_rows, key=lambda r: r.event_date or today_d, reverse=True)[:limit]

        docs: List[Document] = (
            s.query(Document)
            .filter(Document.source_url.isnot(None))
            .order_by(Document.created_at.desc())
            .limit(limit * 3)
            .all()
        )
        report_links: List[ReportLinkOut] = []
        seen = set()
        for d in docs:
            if not d.source_url:
                continue
            k = f"{d.ticker or ''}|{d.source_url}"
            if k in seen:
                continue
            seen.add(k)
            created = d.created_at if isinstance(d.created_at, datetime) else None
            is_new = bool(since_dt and created and created.replace(tzinfo=timezone.utc) > since_dt)
            report_links.append(
                ReportLinkOut(
                    ticker=(d.ticker or "").upper(),
                    company=d.company,
                    doc_id=d.id,
                    source_url=d.source_url,
                    form_type=d.form_type,
                    created_at=(created.isoformat() if created else None),
                    title=(f"{d.form_type} filing" if d.form_type else "Earnings source"),
                    is_new=is_new,
                )
            )
            if len(report_links) >= limit * 2:
                break

        watchlist_tickers = [w.ticker.upper() for w in s.query(Watchlist).all()]
        if not watchlist_tickers:
            watchlist_tickers = sorted(list({(r.ticker or "").upper() for r in rows if r.ticker}))[:limit]

        risk_rows: List[RiskRowOut] = []
        for tk in watchlist_tickers[:limit]:
            tk_events = [r for r in rows if (r.ticker or "").upper() == tk]
            tk_events = sorted(tk_events, key=lambda r: r.event_date or today_d)
            ev = tk_events[0] if tk_events else None
            if ev and ev.event_date:
                eta_dt = datetime(ev.event_date.year, ev.event_date.month, ev.event_date.day, tzinfo=timezone.utc)
                diff_hours = (eta_dt - now).total_seconds() / 3600.0
                if diff_hours <= 24:
                    risk = "High"
                elif diff_hours <= 72:
                    risk = "Medium"
                else:
                    risk = "Low"
                eta_str = eta_dt.isoformat()
            else:
                risk = "Low"
                eta_str = "No event in range"
            risk_rows.append(
                RiskRowOut(
                    ticker=tk,
                    company=(ev.company if ev else None),
                    eta=eta_str,
                    time_of_day=(ev.time_of_day if ev else None),
                    risk=risk,
                )
            )

        new_reports = [r for r in report_links if r.is_new]
        wl_today = [r for r in today_rows if (r.ticker or "").upper() in set(watchlist_tickers)]

        timeline: List[AlertItemOut] = []
        if wl_today:
            timeline.append(
                AlertItemOut(
                    severity="high",
                    title=f"{len(wl_today)} watchlist names report today",
                    detail="Review BMO/AMC timing and prep scenario notes before market windows.",
                )
            )
        if new_reports:
            timeline.append(
                AlertItemOut(
                    severity="medium",
                    title=f"{len(new_reports)} new reports since last check",
                    detail="Open source filings/transcripts and refresh context in workspace.",
                )
            )
        if not watchlist_tickers:
            timeline.append(
                AlertItemOut(
                    severity="low",
                    title="No watchlist configured",
                    detail="Add core tickers to unlock portfolio risk monitoring.",
                )
            )
        if not timeline:
            timeline.append(
                AlertItemOut(
                    severity="low",
                    title="No immediate risks detected",
                    detail="Pipeline is quiet. Continue monitoring upcoming earnings.",
                )
            )

        return DashboardOverviewOut(
            as_of=now.isoformat(),
            today=[_event_to_out(r) for r in today_rows],
            upcoming=[_event_to_out(r) for r in upcoming_rows],
            reported=[_event_to_out(r) for r in reported_rows],
            report_links=report_links,
            watchlist_risk=risk_rows,
            alert_timeline=timeline,
            counts={
                "today": len(today_rows),
                "upcoming": len(upcoming_rows),
                "reported": len(reported_rows),
                "report_links": len(report_links),
                "watchlist_risk": len(risk_rows),
            },
        )
