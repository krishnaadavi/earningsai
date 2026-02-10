"use client";

import React from "react";
import TickerChip from "../components/TickerChip";
import HighlightCard from "../components/HighlightCard";
import CalendarStrip from "../components/CalendarStrip";
import DetailDrawer from "../components/DetailDrawer";
import ChatDock from "../components/ChatDock";
import Sidebar from "../components/Sidebar";
import { fetchWatchlist, addToWatchlist, removeFromWatchlist, fetchWatchlistEvents, WatchEvent } from "../lib/watchlist";
import { fetchMarketMovers, Mover } from "../lib/market";
import ChatPanel from "../components/ChatPanel";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';

// Backend shapes
type Event = {
  id: string;
  ticker: string;
  company?: string | null;
  event_date: string; // ISO
  time_of_day?: string | null; // BMO/AMC
  status?: string | null;
};

type Highlight = {
  id: string;
  ticker: string;
  company?: string | null;
  summary: any;
  rank_score?: number | null;
  created_at: string;
};

type TradeIdea = {
  ticker: string;
  title: string;
  thesis: string;
  action: string;
  confidence: 'High' | 'Medium' | 'Low';
  catalyst?: string | null;
  timeframe?: string | null;
};

// EPS summaries (from /earnings/summaries/today)
type EPSSummaryItem = {
  period: string;
  reported_eps?: number | null;
  estimated_eps?: number | null;
  surprise?: number | null;
  surprise_pct?: number | null;
  provider?: string | null;
};
type EarningsSummary = {
  ticker: string;
  company?: string | null;
  latest?: EPSSummaryItem | null;
  eps: EPSSummaryItem[];
  sources: string[];
};

type AlertPrefs = {
  preMarket: boolean;
  postMarket: boolean;
  notifyEmail: boolean;
  notifyInApp: boolean;
};

const ALERT_PREFS_KEY = 'earnings-alert-preferences';

function isoDate(d: Date): string {
  return d.toISOString().split('T')[0];
}

function getWeekStart(d: Date): Date {
  const day = d.getDay(); // 0 Sun .. 6 Sat
  const diff = (day === 0 ? -6 : 1) - day; // shift to Monday
  const start = new Date(d);
  start.setDate(d.getDate() + diff);
  start.setHours(0,0,0,0);
  return start;
}

export default function DashboardPage() {
  const [events, setEvents] = React.useState<Event[]>([]);
  const [loadingEv, setLoadingEv] = React.useState(false);
  const [hToday, setHToday] = React.useState<Highlight[]>([]);
  const [hWeek, setHWeek] = React.useState<Highlight[]>([]);
  const [loadingH, setLoadingH] = React.useState(false);
  const [error, setError] = React.useState<string>("");

  const [weekStart, setWeekStart] = React.useState<Date>(() => getWeekStart(new Date()));
  const [selectedDate, setSelectedDate] = React.useState<Date>(() => new Date());

  // Detail drawer state
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerTicker, setDrawerTicker] = React.useState<string>("");
  const [drawerCompany, setDrawerCompany] = React.useState<string | null>(null);
  const [drawerSummary, setDrawerSummary] = React.useState<any | null>(null);

  // Watchlist & Market Movers
  const [watchlist, setWatchlist] = React.useState<Set<string>>(new Set());
  const [movers, setMovers] = React.useState<Mover[]>([]);
  const [loadingMovers, setLoadingMovers] = React.useState(false);
  const [activeSection, setActiveSection] = React.useState<'none' | 'movers' | 'watchlist'>('none');
  const [wlEvents, setWlEvents] = React.useState<WatchEvent[]>([]);
  const [loadingWlEvents, setLoadingWlEvents] = React.useState(false);
  const [wlFilter, setWlFilter] = React.useState<'all' | 'bmo' | 'amc' | 'tbd'>('all');
  const [moverSort, setMoverSort] = React.useState<'abs' | 'percent' | 'ticker'>('abs');
  const [showChatPanel, setShowChatPanel] = React.useState<boolean>(true);
  const [activeDocId, setActiveDocId] = React.useState<string | null>(null);
  const [alertPrefs, setAlertPrefs] = React.useState<AlertPrefs>({ preMarket: true, postMarket: true, notifyEmail: false, notifyInApp: true });
  const [toast, setToast] = React.useState<string>("");
  const [refreshingWeek, setRefreshingWeek] = React.useState<boolean>(false);
  const [ingestingToday, setIngestingToday] = React.useState<boolean>(false);
  const [lastMetrics, setLastMetrics] = React.useState<any | null>(null);
  // Earnings summaries (API-backed)
  const [sumToday, setSumToday] = React.useState<EarningsSummary[]>([]);
  const [loadingSum, setLoadingSum] = React.useState(false);

  React.useEffect(() => {
    try {
      const saved = localStorage.getItem('docId');
      if (saved) setActiveDocId(saved);
    } catch {}
    const handler = () => {
      try {
        const saved = localStorage.getItem('docId');
        setActiveDocId(saved);
      } catch {}
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  const refreshIngestionStatus = React.useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/metrics/ingestion/last`);
      if (!r.ok) return;
      const j = await r.json();
      setLastMetrics(j);
    } catch {}
  }, []);

  // moved below refreshEvents/refreshHighlights

  const setContextForTicker = async (ticker: string) => {
    const t = (ticker || '').toUpperCase();
    if (!t) return;
    try {
      const r = await fetch(`${API_BASE}/docs/list/by_ticker?ticker=${encodeURIComponent(t)}`);
      if (!r.ok) throw new Error(await r.text());
      const list = await r.json();
      const docId = Array.isArray(list) && list.length > 0 ? list[0].doc_id : null;
      if (docId) {
        try { localStorage.setItem('docId', docId); } catch {}
        setActiveDocId(docId);
        setShowChatPanel(true);
        setToast(`Context set: ${t}`);
      } else {
        setToast(`No document found for ${t}`);
      }
    } catch (e: any) {
      setToast(e?.message || 'Failed to set context');
    }
  };

  React.useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 1800);
    return () => clearTimeout(id);
  }, [toast]);

  React.useEffect(() => {
    try {
      const raw = localStorage.getItem(ALERT_PREFS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        setAlertPrefs((prev) => ({ ...prev, ...parsed }));
      }
    } catch {}
  }, []);

  React.useEffect(() => {
    try {
      localStorage.setItem(ALERT_PREFS_KEY, JSON.stringify(alertPrefs));
    } catch {}
  }, [alertPrefs]);

  const refreshEvents = React.useCallback(async (ws: Date) => {
    setLoadingEv(true);
    setError("");
    try {
      const start = isoDate(ws);
      const end = isoDate(new Date(ws.getFullYear(), ws.getMonth(), ws.getDate() + 6));
      const url = `${API_BASE}/earnings/calendar?start=${start}&end=${end}`;
      let resp = await fetch(url);
      if (!resp.ok) throw new Error(await resp.text());
      let data: Event[] = await resp.json();
      if (!Array.isArray(data) || data.length === 0) {
        // Retry with refresh=1 to populate from provider if missing
        resp = await fetch(`${url}&refresh=1`);
        if (resp.ok) {
          data = await resp.json();
        }
      }
      setEvents(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load calendar');
    } finally {
      setLoadingEv(false);
    }
  }, []);

  const refreshHighlights = React.useCallback(async () => {
    setLoadingH(true);
    setError("");
    try {
      const [rt, rw] = await Promise.all([
        fetch(`${API_BASE}/highlights/today`),
        fetch(`${API_BASE}/highlights/this_week`)
      ]);
      const t: Highlight[] = rt.ok ? await rt.json() : [];
      const w: Highlight[] = rw.ok ? await rw.json() : [];
      setHToday(Array.isArray(t) ? t : []);
      setHWeek(Array.isArray(w) ? w : []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load highlights');
    } finally {
      setLoadingH(false);
    }
  }, []);

  const refreshSummaries = React.useCallback(async () => {
    setLoadingSum(true);
    try {
      const r = await fetch(`${API_BASE}/earnings/summaries/today?limit=12&per_ticker=4`);
      const arr = r.ok ? await r.json() : [];
      setSumToday(Array.isArray(arr) ? arr : []);
    } catch (e: any) {
      setError((prev) => prev || e?.message || 'Failed to load earnings summaries');
    } finally {
      setLoadingSum(false);
    }
  }, []);

  React.useEffect(() => {
    refreshEvents(weekStart);
    refreshHighlights();
    refreshSummaries();
  }, [weekStart, refreshEvents, refreshHighlights, refreshSummaries]);

  React.useEffect(() => {
    refreshIngestionStatus();
  }, [refreshIngestionStatus]);

  // Admin actions
  const refreshWeekFromProvider = async () => {
    if (refreshingWeek) return;
    setRefreshingWeek(true);
    try {
      const start = isoDate(weekStart);
      const end = isoDate(new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + 6));
      const r = await fetch(`${API_BASE}/earnings/calendar?start=${start}&end=${end}&refresh=1`);
      if (!r.ok) throw new Error(await r.text());
      await refreshEvents(weekStart);
      setToast('Week refreshed');
      await refreshIngestionStatus();
    } catch (e: any) {
      setToast(e?.message || 'Failed to refresh week');
    } finally {
      setRefreshingWeek(false);
    }
  };

  const ingestToday = async () => {
    if (ingestingToday) return;
    setIngestingToday(true);
    try {
      const r = await fetch(`${API_BASE}/admin/ingest_today?limit=10`, { method: 'POST' });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      const ok = typeof data?.success === 'number' ? data.success : undefined;
      const req = typeof data?.requested === 'number' ? data.requested : undefined;
      setToast(`Ingested ${ok ?? '?'} of ${req ?? '?'} tickers`);
      await refreshEvents(weekStart);
      await refreshHighlights();
      await refreshIngestionStatus();
    } catch (e: any) {
      setToast(e?.message || 'Failed to ingest today');
    } finally {
      setIngestingToday(false);
    }
  };

  // Load watchlist on mount
  React.useEffect(() => {
    (async () => {
      const items = await fetchWatchlist();
      const s = new Set<string>();
      for (const it of items) s.add((it.ticker || '').toUpperCase());
      setWatchlist(s);
    })();
  }, []);

  const toggleWatchlist = async (ticker: string) => {
    const tk = (ticker || '').toUpperCase();
    if (!tk) return;
    let ok = false;
    if (watchlist.has(tk)) {
      ok = await removeFromWatchlist(tk);
      if (ok) {
        const s = new Set(watchlist); s.delete(tk); setWatchlist(s);
      }
    } else {
      ok = await addToWatchlist(tk);
      if (ok) {
        const s = new Set(watchlist); s.add(tk); setWatchlist(s);
      }
    }
  };

  const showMarketMovers = async () => {
    setActiveSection('movers');
    setLoadingMovers(true);
    try {
      const arr = await fetchMarketMovers(20);
      setMovers(arr || []);
    } finally {
      setLoadingMovers(false);
    }
  };

  const showWatchlist = async () => {
    setActiveSection('watchlist');
    setLoadingWlEvents(true);
    try {
      const start = isoDate(weekStart);
      const end = isoDate(new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + 6));
      const arr = await fetchWatchlistEvents(start, end);
      setWlEvents(Array.isArray(arr) ? arr : []);
    } finally {
      setLoadingWlEvents(false);
    }
  };

  const eventsForSelected = React.useMemo(() => {
    const key = isoDate(selectedDate);
    return (events || []).filter(ev => (ev.event_date || '').startsWith(key));
  }, [events, selectedDate]);

  const groupByTime = React.useMemo(() => {
    const bmo: Event[] = [];
    const amc: Event[] = [];
    const tbd: Event[] = [];
    for (const ev of eventsForSelected) {
      const t = (ev.time_of_day || '').toUpperCase();
      if (t === 'BMO') bmo.push(ev);
      else if (t === 'AMC') amc.push(ev);
      else tbd.push(ev);
    }
    return { bmo, amc, tbd };
  }, [eventsForSelected]);

  const pageStyle: React.CSSProperties = {
    maxWidth: 1100, margin: '24px auto', padding: '0 16px',
    fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto', color: 'var(--color-text)',
  };

  // Counts for sidebar quick actions
  const todayKey = isoDate(new Date());
  const todayCount = React.useMemo(() => (events || []).filter(ev => (ev.event_date || '').startsWith(todayKey)).length, [events, todayKey]);
  const weekCount = React.useMemo(() => (events || []).length, [events]);

  const nextEvent = React.useMemo(() => {
    const upcoming = (events || []).filter((ev) => {
      if (!ev?.event_date) return false;
      const dt = new Date(ev.event_date);
      if (Number.isNaN(dt.getTime())) return false;
      const now = new Date();
      return dt >= now;
    });
    upcoming.sort((a, b) => {
      const da = new Date(a.event_date || 0).getTime();
      const db = new Date(b.event_date || 0).getTime();
      return da - db;
    });
    return upcoming[0] || null;
  }, [events]);

  const watchlistUpcomingCount = React.useMemo(() => {
    if (!watchlist || watchlist.size === 0) return 0;
    const now = new Date();
    return (events || []).filter((ev) => {
      if (!ev?.event_date) return false;
      const dt = new Date(ev.event_date);
      if (Number.isNaN(dt.getTime())) return false;
      const ticker = (ev.ticker || '').toUpperCase();
      return watchlist.has(ticker) && dt >= now;
    }).length;
  }, [events, watchlist]);

  const topHighlight = React.useMemo(() => {
    if (Array.isArray(hToday) && hToday.length > 0) return hToday[0];
    if (Array.isArray(hWeek) && hWeek.length > 0) return hWeek[0];
    return null;
  }, [hToday, hWeek]);

  const derivedIdeas = React.useMemo<TradeIdea[]>(() => {
    const ideas: TradeIdea[] = [];

    if (topHighlight) {
      const score = typeof topHighlight.rank_score === 'number' ? topHighlight.rank_score : 0.5;
      const bullish = score >= 0.65;
      ideas.push({
        ticker: topHighlight.ticker,
        title: `${(topHighlight.ticker || '').toUpperCase()} post-call setup`,
        thesis: topHighlight.summary?.bullets?.[0] || 'Review call transcript to identify positioning cues before the next session.',
        action: bullish ? 'Consider long bias' : 'Monitor for confirmation',
        confidence: bullish ? 'High' : score >= 0.5 ? 'Medium' : 'Low',
        catalyst: topHighlight.summary?.bullets?.[1] || topHighlight.company || null,
        timeframe: 'Next 1-3 sessions',
      });
    }

    if (Array.isArray(movers) && movers.length > 0) {
      const sorted = [...movers].sort((a, b) => Math.abs((b.change_percent ?? 0)) - Math.abs((a.change_percent ?? 0)));
      const strongMover = sorted[0];
      if (strongMover) {
        const pct = strongMover.change_percent ?? 0;
        ideas.push({
          ticker: strongMover.ticker,
          title: `${(strongMover.ticker || '').toUpperCase()} volatility setup`,
          thesis: `Move of ${pct.toFixed(2)}% detected. Gauge implied volatility direction and prep straddle/strangle candidates ahead of earnings.`,
          action: Math.abs(pct) >= 5 ? 'Evaluate volatility strategies' : 'Set alert for continuation',
          confidence: Math.abs(pct) >= 5 ? 'Medium' : 'Low',
          catalyst: strongMover.company || 'Market mover insight',
          timeframe: 'Pre-earnings window',
        });
      }
    }

    if (watchlist.size > 0) {
      const upcoming = (events || [])
        .filter((ev) => watchlist.has((ev.ticker || '').toUpperCase()))
        .sort((a, b) => new Date(a.event_date || 0).getTime() - new Date(b.event_date || 0).getTime());
      if (upcoming.length > 0) {
        const ev = upcoming[0];
        const eventDate = ev?.event_date ? new Date(ev.event_date).toLocaleString(undefined, { month: 'short', day: 'numeric' }) : null;
        ideas.push({
          ticker: ev.ticker,
          title: `${(ev.ticker || '').toUpperCase()} watchlist focus`,
          thesis: 'Align prep notes, consensus deltas, and set alerts for BMO/AMC gap risk.',
          action: 'Build earnings game plan',
          confidence: 'Medium',
          catalyst: ev.time_of_day ? `${ev.time_of_day} call${eventDate ? ` · ${eventDate}` : ''}` : eventDate,
          timeframe: 'Upcoming report',
        });
      }
    }

    if (ideas.length === 0 && nextEvent) {
      ideas.push({
        ticker: nextEvent.ticker,
        title: `${(nextEvent.ticker || '').toUpperCase()} earnings watch`,
        thesis: 'No transcript yet—gather consensus estimates and prepare questions for the call.',
        action: 'Collect research notes',
        confidence: 'Low',
        catalyst: nextEvent.event_date || null,
        timeframe: 'Upcoming report',
      });
    }

    const uniqueByTicker: Record<string, TradeIdea> = {};
    for (const idea of ideas) {
      const key = (idea.ticker || '').toUpperCase();
      if (!uniqueByTicker[key]) uniqueByTicker[key] = idea;
    }
    return Object.values(uniqueByTicker).slice(0, 4);
  }, [topHighlight, movers, watchlist, events, nextEvent]);

  const alertTiles = React.useMemo(() => {
    const alerts: { label: string; detail: string; cta?: () => void }[] = [];
    if (watchlistUpcomingCount > 0) {
      alerts.push({
        label: `${watchlistUpcomingCount} watchlist events this week`,
        detail: alertPrefs.preMarket || alertPrefs.postMarket
          ? 'Alerts will highlight pre/post-market windows based on your preference.'
          : 'Enable alerts below to prep for BMO/AMC gaps.',
      });
    }
    if (!activeDocId) {
      alerts.push({
        label: 'No active context',
        detail: 'Open a highlight card and click “Set context” for tailored prompts.',
      });
    }
    if (!alertPrefs.notifyEmail && !alertPrefs.notifyInApp) {
      alerts.push({
        label: 'Notifications disabled',
        detail: 'Turn on in-app or email alerts to capture day-of reminders.',
      });
    }
    if (alerts.length === 0) {
      alerts.push({ label: 'All clear', detail: 'You’re tracking everything for this week. Set custom alerts soon.' });
    }
    return alerts;
  }, [watchlistUpcomingCount, activeDocId, alertPrefs]);

  const toggleAlertPref = React.useCallback((key: keyof AlertPrefs) => {
    setAlertPrefs((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const summaryCardStyle: React.CSSProperties = {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    boxShadow: '0 12px 28px rgba(15,23,42,0.08)'
  };
  const summaryGridStyle: React.CSSProperties = {
    display: 'grid',
    gap: 12,
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))'
  };
  const summaryTileStyle: React.CSSProperties = {
    borderRadius: 14,
    border: '1px solid var(--color-border)',
    background: 'var(--color-elevated)',
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 6
  };
  const summaryLabel: React.CSSProperties = { fontSize: 12, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 0.5 };
  const summaryValue: React.CSSProperties = { fontSize: 24, fontWeight: 700, color: 'var(--color-text)' };
  const summarySubText: React.CSSProperties = { fontSize: 13, color: 'var(--color-muted)', lineHeight: 1.4 };

  return (
    <>
    <main style={pageStyle}>
      <div style={{ display: 'flex', gap: 16 }}>
        <Sidebar
          todayCount={todayCount}
          weekCount={weekCount}
          watchlistCount={watchlist.size}
          onNewChat={() => setShowChatPanel(true)}
          onGoToday={() => setSelectedDate(new Date())}
          onGoThisWeek={() => setWeekStart(getWeekStart(new Date()))}
          onGoMarketMovers={showMarketMovers}
          onGoWatchlist={showWatchlist}
        />
        <div style={{ flex: 1 }}>
      <section style={summaryCardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text)' }}>Today’s Earnings Prep</div>
            <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>Stay ahead of surprise risk with upcoming calls, highlights, and watchlist coverage.</div>
          </div>
          <button
            onClick={() => setShowChatPanel(true)}
            style={{ padding: '8px 14px', borderRadius: 999, border: '1px solid var(--color-border)', background: 'var(--color-elevated)', color: 'var(--color-text)', fontSize: 13 }}
          >
            Ask the agent
          </button>
        </div>
        <div style={summaryGridStyle}>
          <div style={summaryTileStyle}>
            <span style={summaryLabel}>Today’s earnings</span>
            <span style={summaryValue}>{todayCount}</span>
            <span style={summarySubText}>Events reporting today (BMO + AMC)</span>
          </div>
          <div style={summaryTileStyle}>
            <span style={summaryLabel}>Next on deck</span>
            <span style={summaryValue}>{nextEvent ? nextEvent.ticker : '—'}</span>
            <span style={summarySubText}>
              {nextEvent
                ? `${new Date(nextEvent.event_date).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}${nextEvent.time_of_day ? ` · ${nextEvent.time_of_day}` : ''}`
                : 'No upcoming events scheduled'}
            </span>
          </div>
          <div style={summaryTileStyle}>
            <span style={summaryLabel}>Watchlist coverage</span>
            <span style={summaryValue}>{watchlist.size}</span>
            <span style={summarySubText}>{watchlist.size > 0 ? `${watchlistUpcomingCount} upcoming this week` : 'Add tickers to your watchlist'}</span>
          </div>
          <div style={summaryTileStyle}>
            <span style={summaryLabel}>Latest highlight</span>
            <span style={summaryValue}>{topHighlight ? topHighlight.ticker : '—'}</span>
            <span style={summarySubText}>
              {topHighlight?.summary?.bullets?.[0]
                ? topHighlight.summary.bullets[0]
                : 'Ingest a symbol or refresh to pull the newest summaries.'}
            </span>
          </div>
        </div>
      </section>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0, color: 'var(--color-text)' }}>Earnings Dashboard</h1>
        <span style={{ fontSize: 11, borderRadius: 999, border: '1px solid var(--color-border)', padding: '2px 8px', color: 'var(--color-muted)', background: 'var(--color-elevated)' }}>
          Revamp build: 2026-02-09
        </span>
      </div>
      <div style={{ color: 'var(--color-muted)', marginBottom: 16 }}>Backend base: <code>{API_BASE}</code></div>

      {/* Prominent Chat Panel */}
      {showChatPanel && (
        <ChatPanel onClose={() => setShowChatPanel(false)} />
      )}

      {/* Calendar strip */}
      <section style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>This Week</h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => { const prev = new Date(weekStart); prev.setDate(prev.getDate() - 7); setWeekStart(getWeekStart(prev)); }}>
              ◀ Prev
            </button>
            <button onClick={() => setWeekStart(getWeekStart(new Date()))}>Today</button>
            <button onClick={() => { const next = new Date(weekStart); next.setDate(next.getDate() + 7); setWeekStart(getWeekStart(next)); }}>
              Next ▶
            </button>
            <button
              onClick={refreshWeekFromProvider}
              disabled={refreshingWeek}
              title="Refresh from provider"
              style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-elevated)', color: 'var(--color-text)', opacity: refreshingWeek ? 0.6 : 1 }}
            >
              {refreshingWeek ? 'Refreshing…' : 'Refresh'}
            </button>
            <button
              onClick={ingestToday}
              disabled={ingestingToday}
              title="Ingest today's earnings PDFs"
              style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-elevated)', color: 'var(--color-text)', opacity: ingestingToday ? 0.6 : 1 }}
            >
              {ingestingToday ? 'Ingesting…' : 'Ingest Today'}
            </button>
          </div>
        </div>
        {lastMetrics?.last_ingest && (
          <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 8 }}>
            Last ingest: {new Date(lastMetrics.last_ingest.created_at).toLocaleString()} • {lastMetrics.last_ingest.success}/{lastMetrics.last_ingest.requested} • {(lastMetrics.last_ingest.tickers || []).slice(0,12).join(', ')}{(lastMetrics.last_ingest.tickers || []).length > 12 ? ` +${(lastMetrics.last_ingest.tickers || []).length - 12}` : ''} • <a href="/ingestion" style={{ color: 'var(--color-muted)' }}>details</a>
          </div>
        )}
        <CalendarStrip
          weekStart={weekStart}
          events={events}
          selectedDate={selectedDate}
          onSelectDate={setSelectedDate}
        />
      </section>

      {/* Market Movers */}
      {activeSection === 'movers' && (
        <section style={{ marginTop: 16 }}>
          <h2 style={{ margin: '8px 0' }}>Market Movers</h2>
          {/* Sorting controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: 'var(--color-muted)' }}>Sort:</span>
            <button
              onClick={() => setMoverSort('abs')}
              style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: moverSort==='abs' ? 'var(--color-primary)' : 'var(--color-elevated)', color: moverSort==='abs' ? 'var(--color-primary-contrast)' : 'var(--color-text)' }}
            >Abs %</button>
            <button
              onClick={() => setMoverSort('percent')}
              style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: moverSort==='percent' ? 'var(--color-primary)' : 'var(--color-elevated)', color: moverSort==='percent' ? 'var(--color-primary-contrast)' : 'var(--color-text)' }}
            >% Change</button>
            <button
              onClick={() => setMoverSort('ticker')}
              style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: moverSort==='ticker' ? 'var(--color-primary)' : 'var(--color-elevated)', color: moverSort==='ticker' ? 'var(--color-primary-contrast)' : 'var(--color-text)' }}
            >Ticker</button>
          </div>
          {loadingMovers ? (
            <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
          ) : (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {(() => {
                const list = [...(movers || [])];
                list.sort((a, b) => {
                  if (moverSort === 'ticker') return (a.ticker || '').localeCompare(b.ticker || '');
                  const ap = typeof a.change_percent === 'number' ? a.change_percent : -Infinity;
                  const bp = typeof b.change_percent === 'number' ? b.change_percent : -Infinity;
                  if (moverSort === 'percent') return Math.abs(bp) - Math.abs(ap); // desc by % magnitude (like abs), but name aligns
                  // 'abs' default: same as above, explicit for clarity
                  return Math.abs(bp) - Math.abs(ap);
                });
                return list;
              })().map((m, idx) => (
                <TickerChip
                  key={m.ticker + idx}
                  ticker={m.ticker}
                  company={m.company || null}
                  tags={[
                    typeof m.change_percent === 'number'
                      ? `${m.change_percent >= 0 ? 'up' : 'down'} ${Math.abs(m.change_percent).toFixed(2)}%`
                      : '—',
                  ]}
                  watchlisted={watchlist.has(m.ticker)}
                  onToggleWatchlist={() => toggleWatchlist(m.ticker)}
                  onSetContext={() => setContextForTicker(m.ticker)}
                />
              ))}
              {(movers || []).length === 0 && (
                <div style={{ color: 'var(--color-muted)' }}>No movers available.</div>
              )}
            </div>
          )}
        </section>
      )}

      {/* My Watchlist */}
      {activeSection === 'watchlist' && (
        <section style={{ marginTop: 16 }}>
          <h2 style={{ margin: '8px 0' }}>My Watchlist</h2>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Array.from(watchlist).map((t) => (
              <TickerChip key={t} ticker={t} company={null} tags={[]} watchlisted={true} onToggleWatchlist={() => toggleWatchlist(t)} onSetContext={() => setContextForTicker(t)} />
            ))}
            {watchlist.size === 0 && <div style={{ color: 'var(--color-muted)' }}>No tickers in watchlist yet.</div>}
          </div>

          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: '8px 0' }}>Upcoming This Week</h3>
            {/* Filters */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--color-muted)' }}>Filter:</span>
              <button onClick={() => setWlFilter('all')} style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: wlFilter==='all' ? 'var(--color-primary)' : 'var(--color-elevated)', color: wlFilter==='all' ? 'var(--color-primary-contrast)' : 'var(--color-text)' }}>All</button>
              <button onClick={() => setWlFilter('bmo')} style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: wlFilter==='bmo' ? 'var(--color-primary)' : 'var(--color-elevated)', color: wlFilter==='bmo' ? 'var(--color-primary-contrast)' : 'var(--color-text)' }}>BMO</button>
              <button onClick={() => setWlFilter('amc')} style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: wlFilter==='amc' ? 'var(--color-primary)' : 'var(--color-elevated)', color: wlFilter==='amc' ? 'var(--color-primary-contrast)' : 'var(--color-text)' }}>AMC</button>
              <button onClick={() => setWlFilter('tbd')} style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--color-border)', background: wlFilter==='tbd' ? 'var(--color-primary)' : 'var(--color-elevated)', color: wlFilter==='tbd' ? 'var(--color-primary-contrast)' : 'var(--color-text)' }}>TBD</button>
            </div>
            {loadingWlEvents ? (
              <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
            ) : (
              (() => {
                const groups: Record<string, WatchEvent[]> = {};
                const matchesFilter = (t: string | null | undefined) => {
                  const u = (t || '').toUpperCase();
                  if (wlFilter === 'all') return true;
                  if (wlFilter === 'bmo') return u === 'BMO';
                  if (wlFilter === 'amc') return u === 'AMC';
                  return u !== 'BMO' && u !== 'AMC';
                };
                for (const ev of wlEvents || []) {
                  if (!matchesFilter(ev.time_of_day)) continue;
                  const key = (ev.event_date || '').split('T')[0];
                  if (!groups[key]) groups[key] = [];
                  groups[key].push(ev);
                }
                const days = Object.keys(groups).sort();
                if (days.length === 0) return <div style={{ color: 'var(--color-muted)' }}>No upcoming events for your watchlist this week.</div>;
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {days.map((d) => (
                      <div key={d} style={{ border: '1px solid var(--color-border)', borderRadius: 12, padding: 12 }}>
                        <div style={{ fontWeight: 600, marginBottom: 8 }}>{d}</div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          {groups[d].map((e) => (
                            <TickerChip key={e.id} ticker={e.ticker} company={e.company || null} tags={[e.time_of_day || 'TBD']} watchlisted={watchlist.has(e.ticker)} onToggleWatchlist={() => toggleWatchlist(e.ticker)} onSetContext={() => setContextForTicker(e.ticker)} />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()
            )}
          </div>
        </section>
      )}

      {/* Today BMO/AMC */}
      <section style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>Today (BMO)</h3>
          {loadingEv ? (
            <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
          ) : (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {groupByTime.bmo.map((e) => (
                <TickerChip key={e.id} ticker={e.ticker} company={e.company} tags={[e.time_of_day || '']} watchlisted={watchlist.has(e.ticker)} onToggleWatchlist={() => toggleWatchlist(e.ticker)} onSetContext={() => setContextForTicker(e.ticker)} />
              ))}
              {groupByTime.bmo.length === 0 && <div style={{ color: 'var(--color-muted)' }}>No events</div>}
            </div>
          )}
        </div>
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>Today (AMC)</h3>
          {loadingEv ? (
            <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
          ) : (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {groupByTime.amc.map((e) => (
                <TickerChip key={e.id} ticker={e.ticker} company={e.company} tags={[e.time_of_day || '']} watchlisted={watchlist.has(e.ticker)} onToggleWatchlist={() => toggleWatchlist(e.ticker)} onSetContext={() => setContextForTicker(e.ticker)} />
              ))}
              {groupByTime.amc.length === 0 && <div style={{ color: 'var(--color-muted)' }}>No events</div>}
            </div>
          )}
        </div>
        {/* Optional third card for events with unknown time_of_day */}
        {groupByTime.tbd.length > 0 && (
          <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 16 }}>
            <h3 style={{ marginTop: 0 }}>Today (TBD)</h3>
            {loadingEv ? (
              <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
            ) : (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {groupByTime.tbd.map((e) => (
                  <TickerChip key={e.id} ticker={e.ticker} company={e.company} tags={[e.time_of_day || 'TBD']} watchlisted={watchlist.has(e.ticker)} onToggleWatchlist={() => toggleWatchlist(e.ticker)} onSetContext={() => setContextForTicker(e.ticker)} />
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Today's Earnings Summaries */}
      <section style={{ marginTop: 16 }}>
        <h2 style={{ margin: '8px 0' }}>Today’s Earnings Summaries</h2>
        {loadingSum ? (
          <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
            {(sumToday || []).map((s) => {
              const latest = s?.latest as EPSSummaryItem | undefined;
              const rep = typeof latest?.reported_eps === 'number' ? latest?.reported_eps : null;
              const est = typeof latest?.estimated_eps === 'number' ? latest?.estimated_eps : null;
              const spr = typeof latest?.surprise === 'number' ? latest?.surprise : null;
              const sprp = typeof latest?.surprise_pct === 'number' ? latest?.surprise_pct : null;
              const line = [
                rep != null ? `EPS ${rep.toFixed(2)}` : null,
                est != null ? `vs est ${est.toFixed(2)}` : null,
                spr != null || sprp != null ? `surprise ${(spr ?? 0) > 0 ? '+' : ''}${spr != null ? spr.toFixed(2) : ''}${sprp != null ? ` (${sprp.toFixed(1)}%)` : ''}` : null,
                latest?.period || null,
              ].filter(Boolean).join(' · ');
              return (
                <div key={s.ticker} style={{ border: '1px solid var(--color-border)', borderRadius: 12, padding: 12, background: 'var(--color-surface)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontWeight: 700, color: 'var(--color-text)' }}>{(s.ticker || '').toUpperCase()}</div>
                    <button onClick={() => setContextForTicker(s.ticker)} style={{ fontSize: 12, border: '1px solid var(--color-border)', borderRadius: 8, padding: '4px 8px', background: 'var(--color-elevated)', color: 'var(--color-text)' }}>Set context</button>
                  </div>
                  {s.company && <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 4 }}>{s.company}</div>}
                  <div style={{ fontSize: 13, marginTop: 8, color: 'var(--color-text)' }}>{line || 'No EPS data'}</div>
                </div>
              );
            })}
            {(sumToday || []).length === 0 && (
              <div style={{ color: 'var(--color-muted)' }}>No summaries yet — provider data may lag for some tickers.</div>
            )}
          </div>
        )}
      </section>

      {/* Highlights */}
      <section style={{ marginTop: 16 }}>
        <h2 style={{ margin: '8px 0' }}>Highlights for Top Stocks</h2>
        {loadingH ? (
          <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
            {hToday.slice(0, 6).map((h) => (
              <HighlightCard
                key={h.id}
                ticker={h.ticker}
                company={h.company || null}
                summary={h.summary}
                rankScore={h.rank_score || null}
                onOpen={() => {
                  setDrawerTicker(h.ticker);
                  setDrawerCompany(h.company || null);
                  setDrawerSummary(h.summary);
                  setDrawerOpen(true);
                }}
                onSetContextTicker={() => setContextForTicker(h.ticker)}
              />
            ))}
            {hToday.length === 0 && (
              <div style={{ color: 'var(--color-muted)' }}>No highlights yet — ingest a symbol from the main page or wait for events.</div>
            )}
          </div>
        )}
      </section>

      {/* Trade ideas & alerts */}
      <section style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 12, alignItems: 'start' }}>
        <div style={{ border: '1px solid var(--color-border)', borderRadius: 12, padding: 16, background: 'var(--color-surface)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0 }}>Trade set-ups</h2>
            <span style={{ fontSize: 12, color: 'var(--color-muted)' }}>Experimental</span>
          </div>
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {derivedIdeas.map((idea, idx) => (
              <div key={idx} style={{ border: '1px solid var(--color-border)', borderRadius: 12, padding: 12, background: 'var(--color-elevated)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <div style={{ fontWeight: 600 }}>{idea.title}</div>
                  <span style={{ fontSize: 11, borderRadius: 999, border: '1px solid var(--color-border)', padding: '2px 8px', color: 'var(--color-muted)' }}>{idea.confidence} confidence</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 6 }}>{idea.thesis}</div>
                {idea.catalyst && <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 6 }}>Catalyst: {idea.catalyst}</div>}
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button
                    onClick={() => {
                      setDrawerTicker(idea.ticker);
                      setDrawerCompany(null);
                      setDrawerSummary(null);
                      setDrawerOpen(true);
                    }}
                    style={{ borderRadius: 10, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', padding: '6px 10px' }}
                  >
                    Open detail
                  </button>
                  <button onClick={() => setShowChatPanel(true)} style={{ borderRadius: 10, border: 'none', background: 'linear-gradient(90deg, var(--color-primary), #8b5cf6)', color: 'var(--color-primary-contrast)', padding: '6px 12px' }}>Ask agent</button>
                </div>
              </div>
            ))}
            {derivedIdeas.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>No ideas yet—try ingesting a report or loading market movers.</div>
            )}
          </div>
        </div>
        <div style={{ border: '1px solid var(--color-border)', borderRadius: 12, padding: 16, background: 'var(--color-surface)', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <h2 style={{ margin: 0 }}>Alerts</h2>
          {alertTiles.map((alert, idx) => (
            <div key={idx} style={{ border: '1px dashed var(--color-border)', borderRadius: 10, padding: 12, background: 'var(--color-elevated)' }}>
              <div style={{ fontWeight: 600 }}>{alert.label}</div>
              <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 4 }}>{alert.detail}</div>
            </div>
          ))}
          <div style={{ border: '1px solid var(--color-border)', borderRadius: 10, padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontWeight: 600 }}>Notification preferences</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              <input type="checkbox" checked={alertPrefs.preMarket} onChange={() => toggleAlertPref('preMarket')} />
              Pre-market alerts (BMO)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              <input type="checkbox" checked={alertPrefs.postMarket} onChange={() => toggleAlertPref('postMarket')} />
              Post-market alerts (AMC)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              <input type="checkbox" checked={alertPrefs.notifyInApp} onChange={() => toggleAlertPref('notifyInApp')} />
              In-app banners
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              <input type="checkbox" checked={alertPrefs.notifyEmail} onChange={() => toggleAlertPref('notifyEmail')} />
              Email reminders (coming soon)
            </label>
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>Notifications will sync with Google sign-in in a later release.</div>
        </div>
      </section>

      {/* Detail Drawer */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        ticker={drawerTicker}
        company={drawerCompany || undefined}
        initialSummary={drawerSummary}
        onSetContext={(docId: string) => {
          try { localStorage.setItem('docId', docId); } catch {}
          setActiveDocId(docId);
          setShowChatPanel(true);
          setToast('Context set');
        }}
      />
        </div>
      </div>
    </main>

    {/* Persistent Chat Dock (hide when main panel is open) */}
    {!showChatPanel && <ChatDock />}

    {/* Tiny toast */}
    {toast && (
      <div style={{ position: 'fixed', bottom: 16, right: 16, background: 'var(--color-elevated)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 10, padding: '8px 12px', boxShadow: '0 8px 24px rgba(15,23,42,0.15)', zIndex: 100 }}>
        {toast}
      </div>
    )}
    </>
  );
}
