"use client";

import React from "react";
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend);

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';

type DocSummary = {
  doc_id: string;
  chunk_count: number;
  ticker?: string | null;
  company?: string | null;
  filename?: string | null;
  created_at?: string | null;
};

type SeriesItem = { labels: string[]; values: number[] };
type MetricsItem = {
  name: string;
  value: number;
  unit?: string;
  period?: string | null;
  annotations?: string[] | null;
};
type GuidanceItem = {
  id?: string;
  metric?: string | null;
  period?: string | null;
  value_low?: number | null;
  value_high?: number | null;
  value_point?: number | null;
  unit?: string | null;
  outlook_note?: string | null;
  confidence?: string | null;
  detail?: string | null;
  citations?: { section?: string | null; page?: number; snippet: string }[];
};

type Props = {
  open: boolean;
  onClose: () => void;
  ticker: string;
  company?: string | null;
  initialSummary?: any | null; // highlight summary with bullets if present
  onSetContext?: (docId: string) => void;
};

export default function DetailDrawer({ open, onClose, ticker, company, initialSummary, onSetContext }: Props) {
  const [summary, setSummary] = React.useState<any | null>(initialSummary || null);
  const [docs, setDocs] = React.useState<DocSummary[]>([]);
  const [loadingDocs, setLoadingDocs] = React.useState(false);
  const [series, setSeries] = React.useState<Record<string, SeriesItem>>({});
  const [selectedDocId, setSelectedDocId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string>("");
  const [metrics, setMetrics] = React.useState<Record<string, MetricsItem>>({});
  const [metricsLoading, setMetricsLoading] = React.useState(false);
  const [guidance, setGuidance] = React.useState<GuidanceItem[]>([]);
  const [guidanceLoading, setGuidanceLoading] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    setError("");
    // If no summary, fetch latest highlight for ticker
    const loadSummary = async () => {
      try {
        if (initialSummary) return;
        const resp = await fetch(`${API_BASE}/ticker/${encodeURIComponent(ticker)}/highlights`);
        if (resp.ok) {
          const arr = await resp.json();
          if (Array.isArray(arr) && arr.length > 0) setSummary(arr[0].summary || null);
        }
      } catch {}
    };
    // Load docs list by ticker
    const loadDocs = async () => {
      try {
        setLoadingDocs(true);
        const r = await fetch(`${API_BASE}/docs/list/by_ticker?ticker=${encodeURIComponent(ticker)}`);
        if (!r.ok) throw new Error(await r.text());
        const list: DocSummary[] = await r.json();
        setDocs(list || []);
        if (list && list.length > 0) {
          setSelectedDocId(list[0].doc_id);
        }
      } catch (e: any) {
        setError(e?.message || 'Failed to load docs');
      } finally {
        setLoadingDocs(false);
      }
    };
    loadSummary();
    loadDocs();
  }, [open, ticker, initialSummary]);

  React.useEffect(() => {
    if (!open || !selectedDocId) return;
    const loadSeries = async () => {
      try {
        const metrics = ["revenue", "eps_gaap"]; // simple mini charts
        const resp = await fetch(`${API_BASE}/series`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doc_id: selectedDocId, metrics })
        });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        setSeries(data.series || {});
      } catch (e: any) {
        setError(e?.message || 'Failed to load series');
      }
    };
    loadSeries();
  }, [open, selectedDocId]);

  React.useEffect(() => {
    if (!open || !selectedDocId) return;
    let aborted = false;
    const loadMetrics = async () => {
      setMetricsLoading(true);
      try {
        const resp = await fetch(`${API_BASE}/metrics`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doc_id: selectedDocId }),
        });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        if (!aborted) setMetrics(data.metrics || {});
      } catch (e: any) {
        if (!aborted) setError(e?.message || 'Failed to load metrics');
      } finally {
        if (!aborted) setMetricsLoading(false);
      }
    };
    loadMetrics();
    return () => { aborted = true; };
  }, [open, selectedDocId]);

  React.useEffect(() => {
    if (!open || !selectedDocId) return;
    let aborted = false;
    const normalizeGuidance = (raw: any): GuidanceItem[] => {
      if (!raw) return [];
      const toNumber = (val: any): number | null => {
        if (val === null || val === undefined) return null;
        const num = typeof val === 'number' ? val : Number(val);
        return Number.isFinite(num) ? num : null;
      };
      const arr = Array.isArray(raw)
        ? raw
        : Array.isArray(raw?.guidance)
          ? raw.guidance
          : [];
      return arr
        .map((item: any) => {
          if (item && typeof item === 'object') {
            if ('type' in item || 'range' in item) {
              const range = Array.isArray(item.range) ? item.range : [];
              const low = toNumber(range[0]);
              const high = toNumber(range[1]);
              const val = toNumber(item.value);
              return {
                metric: typeof item.type === 'string' ? item.type : null,
                period: typeof item.period === 'string' ? item.period : null,
                value_low: low,
                value_high: high,
                value_point: val,
                unit: typeof item.unit === 'string' ? item.unit : null,
                outlook_note: typeof item.detail === 'string' ? item.detail : null,
                confidence: 'low',
                citations: Array.isArray(item.citations) ? item.citations : [],
              } as GuidanceItem;
            }
            return {
              id: typeof item.id === 'string' ? item.id : undefined,
              metric: typeof item.metric === 'string' ? item.metric : null,
              period: typeof item.period === 'string' ? item.period : null,
              value_low: toNumber(item.value_low),
              value_high: toNumber(item.value_high),
              value_point: toNumber(item.value_point),
              unit: typeof item.unit === 'string' ? item.unit : null,
              outlook_note: typeof item.outlook_note === 'string' ? item.outlook_note : null,
              confidence: typeof item.confidence === 'string' ? item.confidence : null,
              detail: typeof item.detail === 'string' ? item.detail : null,
              citations: Array.isArray(item.citations) ? item.citations : [],
            } as GuidanceItem;
          }
          if (typeof item === 'string') {
            return { outlook_note: item } as GuidanceItem;
          }
          return null;
        })
        .filter(Boolean) as GuidanceItem[];
    };

    const loadGuidance = async () => {
      setGuidanceLoading(true);
      try {
        const resp = await fetch(`${API_BASE}/guidance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doc_id: selectedDocId }),
        });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        if (!aborted) setGuidance(normalizeGuidance(data));
      } catch (e: any) {
        if (!aborted) setError(e?.message || 'Failed to load guidance');
      } finally {
        if (!aborted) setGuidanceLoading(false);
      }
    };
    loadGuidance();
    return () => { aborted = true; };
  }, [open, selectedDocId]);

  const drawerStyle: React.CSSProperties = {
    position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(560px, 92vw)',
    background: 'var(--color-surface)', color: 'var(--color-text)', borderLeft: '1px solid var(--color-border)',
    transform: open ? 'translateX(0)' : 'translateX(100%)', transition: 'transform .25s ease',
    zIndex: 60, display: 'flex', flexDirection: 'column'
  };
  const headerStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottom: '1px solid var(--color-border)' };
  const bodyStyle: React.CSSProperties = { padding: 16, overflow: 'auto' };

  const bullets: string[] = Array.isArray(summary?.bullets) ? summary.bullets : [];

  return (
    <div style={drawerStyle}>
      <div style={headerStyle}>
        <div>
          <div style={{ fontWeight: 700 }}>{ticker}{company ? ` · ${company}` : ''}</div>
          <div style={{ fontSize: 12, color: '#94a3b8' }}>Detail</div>
        </div>
        <button onClick={onClose} style={{ border: '1px solid var(--color-border)', background: 'var(--color-elevated)', color: 'var(--color-text)', borderRadius: 8, padding: '6px 10px' }}>Close</button>
      </div>
      <div style={bodyStyle}>
        {error && <div style={{ color: 'var(--danger-text)' }}>{error}</div>}

        {/* Summary bullets */}
        <section>
          <h3 style={{ marginTop: 0 }}>Summary</h3>
          {bullets.length > 0 ? (
            <ul>
              {bullets.map((b, i) => <li key={i}>{b}</li>)}
            </ul>
          ) : (
            <div style={{ color: 'var(--color-muted)' }}>No summary yet</div>
          )}
        </section>

        {/* Key metrics */}
        <section style={{ marginTop: 12 }}>
          <h3>Key metrics</h3>
          {metricsLoading ? (
            <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
          ) : (
            (() => {
              const entries = Object.entries(metrics || {});
              if (entries.length === 0) return <div style={{ color: 'var(--color-muted)' }}>No metrics available.</div>;
              const formatVal = (item: MetricsItem) => {
                if (!item || typeof item.value !== 'number') return '—';
                const value = item.value;
                if (!Number.isFinite(value)) return '—';
                const formatted = Math.abs(value) >= 1_000_000_000
                  ? `${(value / 1_000_000_000).toFixed(2)}B`
                  : Math.abs(value) >= 1_000_000
                    ? `${(value / 1_000_000).toFixed(2)}M`
                    : Math.abs(value) >= 1_000
                      ? `${(value / 1_000).toFixed(1)}K`
                      : value.toFixed(2);
                return `${formatted}${item.unit ? ` ${item.unit}` : ''}`;
              };
              const preferredOrder = ['revenue', 'eps_gaap', 'operating_margin', 'free_cash_flow', 'gross_margin'];
              const ordered = entries.sort(([a], [b]) => {
                const ai = preferredOrder.indexOf(a);
                const bi = preferredOrder.indexOf(b);
                if (ai === -1 && bi === -1) return a.localeCompare(b);
                if (ai === -1) return 1;
                if (bi === -1) return -1;
                return ai - bi;
              }).slice(0, 6);
              return (
                <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                  {ordered.map(([key, item]) => (
                    <div key={key || 'metric'} style={{ border: '1px solid var(--color-border)', borderRadius: 10, padding: 12 }}>
                      <div style={{ fontSize: 12, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{(item?.name || key || '').replace(/_/g, ' ')}</div>
                      <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-text)' }}>{formatVal(item)}</div>
                      {item?.period && <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>{item.period}</div>}
                    </div>
                  ))}
                </div>
              );
            })()
          )}
        </section>

        {/* Guidance */}
        <section style={{ marginTop: 12 }}>
          <h3>Forward guidance</h3>
          {guidanceLoading ? (
            <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
          ) : guidance.length === 0 ? (
            <div style={{ color: 'var(--color-muted)' }}>No guidance found.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {guidance.slice(0, 6).map((g, idx) => (
                <div key={g.id || idx} style={{ border: '1px solid var(--color-border)', borderRadius: 8, padding: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ fontWeight: 600 }}>
                    {(g.metric ? g.metric.toUpperCase() : 'Guidance')}{g.period ? ` · ${g.period}` : ''}
                  </div>
                  {(() => {
                    const formatNumber = (val: number | null | undefined) => {
                      if (val === null || val === undefined) return null;
                      const abs = Math.abs(val);
                      if (abs >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(2)}B`;
                      if (abs >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`;
                      if (abs >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
                      return val.toFixed(2);
                    };
                    const parts: string[] = [];
                    if (g.value_low != null || g.value_high != null) {
                      const low = formatNumber(g.value_low ?? null);
                      const high = formatNumber(g.value_high ?? null);
                      if (low && high) parts.push(`${low} – ${high}`);
                      else if (low) parts.push(low);
                      else if (high) parts.push(high);
                    }
                    if (g.value_point != null && parts.length === 0) {
                      const point = formatNumber(g.value_point);
                      if (point) parts.push(point);
                    }
                    if (parts.length > 0) {
                      return (
                        <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>
                          {parts.join(' to ')}{g.unit ? ` ${g.unit}` : ''}
                        </div>
                      );
                    }
                    return null;
                  })()}
                  {g.outlook_note && <div style={{ fontSize: 13 }}>{g.outlook_note}</div>}
                  {g.detail && !g.outlook_note && <div style={{ fontSize: 13 }}>{g.detail}</div>}
                  {g.confidence && <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>Confidence: {g.confidence}</div>}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Mini charts */}
        <section style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {(['revenue', 'eps_gaap'] as const).map((k) => {
            const v = series[k];
            const has = v && (v.labels?.length || 0) > 0;
            const data = has ? {
              labels: v.labels,
              datasets: [{
                label: k.toUpperCase(),
                data: v.values,
                borderColor: k === 'revenue' ? 'rgb(59, 130, 246)' : 'rgb(16, 185, 129)',
                backgroundColor: k === 'revenue' ? 'rgba(59, 130, 246, 0.2)' : 'rgba(16, 185, 129, 0.2)'
              }]
            } : undefined;
            return (
              <div key={k} style={{ border: '1px solid var(--color-border)', borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>{k.toUpperCase()}</div>
                {has ? (
                  <div style={{ marginTop: 6 }}>
                    <Line data={data as any} options={{ plugins: { legend: { display: false } }, elements: { line: { tension: 0.3 } }, scales: { x: { ticks: { display: false } }, y: { ticks: { display: false } } } }} />
                  </div>
                ) : (
                  <div style={{ color: 'var(--color-muted)' }}>No data</div>
                )}
              </div>
            );
          })}
        </section>

        {/* Docs list */}
        <section style={{ marginTop: 12 }}>
          <h3>Documents</h3>
          {loadingDocs ? (
            <div style={{ color: 'var(--color-muted)' }}>Loading…</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(docs || []).map((d) => (
                <div key={d.doc_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', border: '1px solid var(--color-border)', borderRadius: 8, padding: 10 }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>{d.ticker || ticker}{d.company ? ` · ${d.company}` : ''}</div>
                    <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>{d.doc_id.slice(0, 8)}… • {d.chunk_count} chunks</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={() => setSelectedDocId(d.doc_id)} style={{ border: '1px solid var(--color-border)', background: 'var(--color-elevated)', color: 'var(--color-text)', borderRadius: 8, padding: '6px 10px' }}>Set for charts</button>
                    {onSetContext && (
                      <button onClick={() => onSetContext(d.doc_id)} style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)', borderRadius: 8, padding: '6px 10px', border: 'none' }}>Set context</button>
                    )}
                  </div>
                </div>
              ))}
              {(docs || []).length === 0 && (
                <div style={{ color: 'var(--color-muted)' }}>No documents yet for {ticker}</div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
