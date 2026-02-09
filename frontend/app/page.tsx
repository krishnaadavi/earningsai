'use client';

import React from 'react';
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

import ChatDock from './components/ChatDock';

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend);

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';

type UploadResp = { doc_id: string; chunk_count: number };

type Citation = { section?: string | null; page: number; snippet: string };

type AnswerBullet = { text: string; citations: Citation[] };

type QueryResp = { bullets: AnswerBullet[]; chart: { labels?: string[]; values?: number[] } };

type MetricsItem = { name: string; value: number; unit?: string; period?: string | null; citations?: Citation[] };
type MetricsResp = { metrics: Record<string, MetricsItem> };
type SeriesItem = { labels: string[]; values: number[]; citations?: Citation[] };
type SeriesResp = { series: Record<string, SeriesItem> };
type GuidanceResp = { guidance: any };
type BuybacksResp = { buybacks: any };

export default function HomePage() {
  // Render the main UI for the root page. A redirect to /dashboard is handled via vercel.json.
  const [file, setFile] = React.useState<File | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [docId, setDocId] = React.useState<string>('');

  const [question, setQuestion] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [bullets, setBullets] = React.useState<AnswerBullet[]>([]);
  const [chart, setChart] = React.useState<{ labels?: string[]; values?: number[] }>({});
  const [error, setError] = React.useState<string>('');

  type Tab = 'Ask' | 'Metrics' | 'Trends' | 'Guidance' | 'Buybacks' | 'This Week';
  const [activeTab, setActiveTab] = React.useState<Tab>('Ask');

  // Metrics state
  const [metricsLoading, setMetricsLoading] = React.useState(false);
  const [metricsData, setMetricsData] = React.useState<Record<string, MetricsItem>>({});

  // Series state
  const [seriesLoading, setSeriesLoading] = React.useState(false);
  const [seriesData, setSeriesData] = React.useState<Record<string, SeriesItem>>({});
  const [metricsListInput, setMetricsListInput] = React.useState('revenue, eps_gaap, gross_margin');

  // Guidance / Buybacks
  const [guidanceLoading, setGuidanceLoading] = React.useState(false);
  const [guidanceData, setGuidanceData] = React.useState<any[]>([]);
  const [buybacksLoading, setBuybacksLoading] = React.useState(false);
  const [buybacksData, setBuybacksData] = React.useState<any[]>([]);

  // This Week Earnings
  type WeeklyItem = { ticker: string; company: string; date: string };
  const [weeklyLoading, setWeeklyLoading] = React.useState(false);
  const [weekly, setWeekly] = React.useState<WeeklyItem[]>([]);
  const [ingestInputs, setIngestInputs] = React.useState<Record<string, string>>({});
  const [ingestingTicker, setIngestingTicker] = React.useState<string>('');
  const [docsByTicker, setDocsByTicker] = React.useState<Record<string, DocSummary[]>>({});
  const [docsTickerLoading, setDocsTickerLoading] = React.useState<string>('');

  // Documents panel
  type DocSummary = {
    doc_id: string;
    chunk_count: number;
    has_meta?: boolean;
    ticker?: string | null;
    company?: string | null;
    filename?: string | null;
    created_at?: string | null;
  };
  const [docsLoading, setDocsLoading] = React.useState(false);
  const [docs, setDocs] = React.useState<DocSummary[]>([]);

  // Citations modal
  const [citationsOpen, setCitationsOpen] = React.useState(false);
  const [citationsItems, setCitationsItems] = React.useState<Citation[]>([]);

  // Dark mode
  const [darkMode, setDarkMode] = React.useState(false);

  // Toasts
  const [toasts, setToasts] = React.useState<{ id: string; text: string; type: 'success' | 'error' }[]>([]);
  const showToast = (text: string, type: 'success' | 'error' = 'success') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, text, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3200);
  };

  // Persist docId and dark mode preferences
  React.useEffect(() => {
    try {
      const saved = localStorage.getItem('docId');
      if (saved) setDocId(saved);
      const dm = localStorage.getItem('darkMode');
      if (dm === 'true') setDarkMode(true);
    } catch {}
  }, []);

  React.useEffect(() => {
    try {
      if (docId) localStorage.setItem('docId', docId);
    } catch {}
  }, [docId]);

  // Citations modal helpers
  const openCitations = (items: Citation[]) => {
    setCitationsItems(items);
    setCitationsOpen(true);
  };
  const closeCitations = () => setCitationsOpen(false);

  // Load in-memory documents (P0 convenience)
  const onLoadDocs = async () => {
    setDocsLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API_BASE}/docs`);
      if (!resp.ok) throw new Error(await resp.text());
      const data: DocSummary[] = await resp.json();
      setDocs(Array.isArray(data) ? data : []);
      showToast(`Loaded ${Array.isArray(data) ? data.length : 0} documents`, 'success');
    } catch (e: any) {
      setError(e?.message || 'Failed to load docs');
      showToast(e?.message || 'Failed to load docs', 'error');
    } finally {
      setDocsLoading(false);
    }
  };

  const [deleting, setDeleting] = React.useState(false);
  const onDeleteCurrentDoc = async () => {
    if (!docId) return;
    try {
      // simple confirm for now
      if (!window.confirm('Delete current document? This removes it from DB and memory.')) return;
    } catch {}
    setDeleting(true);
    setError('');
    try {
      const resp = await fetch(`${API_BASE}/docs/${encodeURIComponent(docId)}`, { method: 'DELETE' });
      if (!resp.ok) throw new Error(await resp.text());
      // remove from local list and clear selection
      setDocs((prev) => prev.filter((d) => d.doc_id !== docId));
      setDocId('');
      showToast('Deleted document', 'success');
    } catch (e: any) {
      setError(e?.message || 'Failed to delete document');
      showToast(e?.message || 'Failed to delete document', 'error');
    } finally {
      setDeleting(false);
    }
  };

  const onSelectFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
  };

  const onUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const resp = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
      if (!resp.ok) throw new Error(await resp.text());
      const data: UploadResp = await resp.json();
      setDocId(data.doc_id);
      showToast('Uploaded document', 'success');
    } catch (e: any) {
      setError(e?.message || 'Upload failed');
      showToast(e?.message || 'Upload failed', 'error');
    } finally {
      setUploading(false);
    }
  };

  const onAsk = async () => {
    if (!docId || !question.trim()) return;
    setLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId, question }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data: QueryResp = await resp.json();
      setBullets(data.bullets || []);
      setChart(data.chart || {});
    } catch (e: any) {
      setError(e?.message || 'Query failed');
    } finally {
      setLoading(false);
    }
  };

  const onLoadMetrics = async () => {
    if (!docId) return;
    setMetricsLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API_BASE}/metrics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data: MetricsResp = await resp.json();
      setMetricsData(data.metrics || {});
    } catch (e: any) {
      setError(e?.message || 'Failed to load metrics');
    } finally {
      setMetricsLoading(false);
    }
  };

  const onLoadSeries = async () => {
    if (!docId) return;
    setSeriesLoading(true);
    setError('');
    try {
      const metrics = metricsListInput
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const resp = await fetch(`${API_BASE}/series`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId, metrics }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data: SeriesResp = await resp.json();
      setSeriesData(data.series || {});
    } catch (e: any) {
      setError(e?.message || 'Failed to load series');
    } finally {
      setSeriesLoading(false);
    }
  };

  const onLoadGuidance = async () => {
    if (!docId) return;
    setGuidanceLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API_BASE}/guidance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data: GuidanceResp = await resp.json();
      // data.guidance might be an object { guidance: [...] } depending on backend; flatten if needed
      let out = (data as any).guidance;
      if (out && out.guidance) out = out.guidance;
      setGuidanceData(Array.isArray(out) ? out : []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load guidance');
    } finally {
      setGuidanceLoading(false);
    }
  };

  const onLoadBuybacks = async () => {
    if (!docId) return;
    setBuybacksLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API_BASE}/buybacks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data: BuybacksResp = await resp.json();
      let out = (data as any).buybacks;
      if (out && out.buybacks) out = out.buybacks;
      setBuybacksData(Array.isArray(out) ? out : []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load buybacks');
    } finally {
      setBuybacksLoading(false);
    }
  };

  const chartData = React.useMemo(() => {
    return {
      labels: chart.labels || [],
      datasets: [
        {
          label: 'Metric',
          data: chart.values || [],
          borderColor: 'rgb(75, 192, 192)',
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
        },
      ],
    };
  }, [chart]);

  // Build multi-metric series chart
  const seriesChartData = React.useMemo(() => {
    const metrics = Object.keys(seriesData || {});
    if (metrics.length === 0) return { labels: [], datasets: [] as any[] };
    const labels = seriesData[metrics[0]].labels || [];
    const palette = [
      'rgb(75, 192, 192)',
      'rgb(255, 99, 132)',
      'rgb(54, 162, 235)',
      'rgb(255, 159, 64)',
      'rgb(153, 102, 255)',
      'rgb(201, 203, 207)',
    ];
    const datasets = metrics.map((m, i) => ({
      label: m,
      data: seriesData[m].values || [],
      borderColor: palette[i % palette.length],
      backgroundColor: palette[i % palette.length].replace('rgb', 'rgba').replace(')', ', 0.2)'),
    }));
    return { labels, datasets };
  }, [seriesData]);

  const mainStyle = React.useMemo(() => ({
    maxWidth: 1000,
    margin: '40px auto',
    padding: '0 16px',
    fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto',
    background: darkMode ? '#0b0f15' : '#fff',
    color: darkMode ? '#eef2f7' : '#000',
    minHeight: '100vh',
  }), [darkMode]);

  return (
    <main style={mainStyle}>
      <h1>Earnings AI</h1>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div />
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            checked={darkMode}
            onChange={() => setDarkMode((v) => { const nv = !v; try { localStorage.setItem('darkMode', String(nv)); } catch {}; return nv; })}
          />
          Dark mode
        </label>
      </div>
      <p>Upload a single PDF (10-Q/10-K/transcript). Explore metrics, trends, guidance, and buybacks with citations.</p>

      <section style={{ marginTop: 24, padding: 16, border: '1px solid #eee', borderRadius: 8 }}>
        <h2>1) Upload PDF</h2>
        <input type="file" accept="application/pdf" onChange={onSelectFile} />
        <button onClick={onUpload} disabled={!file || uploading} style={{ marginLeft: 12 }}>
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
        {docId && (
          <div style={{ marginTop: 8, color: '#0a0' }}>Uploaded. doc_id: <code>{docId}</code></div>
        )}
      </section>

      <section style={{ marginTop: 24, padding: 16, border: '1px solid #eee', borderRadius: 8 }}>
        <h2>2) Explore</h2>
        <div style={{ margin: '12px 0', padding: 8, background: darkMode ? '#0e1522' : '#f7f9fc', borderRadius: 8, border: '1px solid #eee' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button onClick={onLoadDocs} disabled={docsLoading}>{docsLoading ? 'Loading...' : 'Load Documents'}</button>
            <button onClick={onDeleteCurrentDoc} disabled={!docId || deleting} style={{ color: '#b91c1c' }}>
              {deleting ? 'Deleting...' : 'Delete Current'}
            </button>
            {docs.length > 0 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {docs.map((d) => {
                  const main = d.ticker ? `${d.ticker}${d.company ? ' · ' + d.company : ''}` : (d.filename || `${d.doc_id.slice(0, 8)}…`);
                  const dateStr = d.created_at ? (() => { try { return new Date(d.created_at as string).toLocaleDateString(); } catch { return d.created_at as string; } })() : '';
                  return (
                    <button
                      key={d.doc_id}
                      onClick={() => { setDocId(d.doc_id); try { localStorage.setItem('docId', d.doc_id); } catch {} }}
                      style={{ padding: '6px 10px', border: '1px solid #ddd', borderRadius: 8, background: docId === d.doc_id ? '#cfe8ff' : (darkMode ? '#121826' : '#fff'), textAlign: 'left' }}
                      title={`${main} • ${d.chunk_count} chunks${dateStr ? ' • ' + dateStr : ''}`}
                    >
                      <div style={{ fontWeight: 600 }}>{main}</div>
                      <div style={{ fontSize: 12, color: darkMode ? '#9fb0c9' : '#666' }}>{d.chunk_count} chunks{dateStr ? ` • ${dateStr}` : ''}</div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {(['Ask', 'Metrics', 'Trends', 'Guidance', 'Buybacks', 'This Week'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                border: '1px solid #ddd',
                background: activeTab === t ? '#eef' : '#fff',
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {error && <div style={{ color: 'crimson', marginTop: 8 }}>{error}</div>}

        {activeTab === 'Ask' && (
          <div style={{ marginTop: 16 }}>
            <input
              type="text"
              placeholder="e.g., What were revenue and GAAP EPS?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              style={{ width: '100%', padding: 8 }}
            />
            <button onClick={onAsk} disabled={!docId || loading || !question.trim()} style={{ marginTop: 12 }}>
              {loading ? 'Asking...' : 'Ask'}
            </button>

            {bullets.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h3>Answer</h3>
                <ul>
                  {bullets.map((b, i) => (
                    <li key={i} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, justifyContent: 'space-between', flexWrap: 'wrap' }}>
                        <span>{b.text}</span>
                        {b.citations?.length > 0 && (
                          <button onClick={() => openCitations(b.citations as any)} style={{ fontSize: 12 }}>View sources</button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(chart.labels?.length || 0) > 0 && (
              <div style={{ marginTop: 24 }}>
                <h3>Trend Chart</h3>
                <Line data={chartData} />
              </div>
            )}
          </div>
        )}

        {activeTab === 'Metrics' && (
          <div style={{ marginTop: 16 }}>
            <button onClick={onLoadMetrics} disabled={!docId || metricsLoading}>
              {metricsLoading ? 'Loading...' : 'Load Metrics'}
            </button>
            {Object.keys(metricsData).length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h3>Core Metrics</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
                  {Object.entries(metricsData).map(([key, item]) => (
                    <div key={key} style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12, background: darkMode ? '#121826' : '#fafafa' }}>
                      <div style={{ fontSize: 12, color: darkMode ? '#9fb0c9' : '#666' }}>{key.replace(/_/g, ' ').toUpperCase()}</div>
                      <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>
                        {item.value} {item.unit || ''} {item.period ? `(${item.period})` : ''}
                      </div>
                      {item.citations && item.citations.length > 0 && (
                        <button onClick={() => openCitations(item.citations as any)} style={{ marginTop: 8 }}>View sources</button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'Trends' && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="text"
                value={metricsListInput}
                onChange={(e) => setMetricsListInput(e.target.value)}
                placeholder="Comma-separated metrics (e.g., revenue, eps_gaap, gross_margin)"
                style={{ flex: 1, minWidth: 300, padding: 8 }}
              />
              <button onClick={onLoadSeries} disabled={!docId || seriesLoading}>
                {seriesLoading ? 'Loading...' : 'Load Series'}
              </button>
            </div>
            {Object.keys(seriesData).length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h3>Time Series</h3>
                <Line data={seriesChartData as any} />
              </div>
            )}
          </div>
        )}

        {activeTab === 'Guidance' && (
          <div style={{ marginTop: 16 }}>
            <button onClick={onLoadGuidance} disabled={!docId || guidanceLoading}>
              {guidanceLoading ? 'Loading...' : 'Load Guidance'}
            </button>
            {guidanceData.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h3>Guidance</h3>
                <ul>
                  {guidanceData.map((g: any, i: number) => (
                    <li key={i} style={{ marginBottom: 8 }}>
                      {g.type ? <strong>{g.type}</strong> : null} {g.range ? `: ${g.range[0]} - ${g.range[1]} ${g.unit || ''}` : ''} {g.period ? `(${g.period})` : ''}
                      {g.citations && g.citations.length > 0 && (
                        <ul style={{ fontSize: 12, color: '#555' }}>
                          {g.citations.map((c: Citation, j: number) => (
                            <li key={j}>[{c.section || 'N/A'}, p.{c.page}] — {c.snippet}</li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeTab === 'Buybacks' && (
          <div style={{ marginTop: 16 }}>
            <button onClick={onLoadBuybacks} disabled={!docId || buybacksLoading}>
              {buybacksLoading ? 'Loading...' : 'Load Buybacks'}
            </button>
            {buybacksData.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h3>Buybacks</h3>
                <ul>
                  {buybacksData.map((b: any, i: number) => (
                    <li key={i} style={{ marginBottom: 8 }}>
                      {b.authorization_amount ? <span><strong>Authorized:</strong> {b.authorization_amount} {b.unit || ''} </span> : null}
                      {b.repurchased_amount ? <span><strong>Repurchased:</strong> {b.repurchased_amount} {b.unit || ''} </span> : null}
                      {b.period ? <span>({b.period})</span> : null}
                      {b.citations && b.citations.length > 0 && (
                        <ul style={{ fontSize: 12, color: '#555' }}>
                          {b.citations.map((c: Citation, j: number) => (
                            <li key={j}>[{c.section || 'N/A'}, p.{c.page}] — {c.snippet}</li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeTab === 'This Week' && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <button onClick={async () => {
                setWeeklyLoading(true);
                setError('');
                try {
                  const resp = await fetch(`${API_BASE}/weekly`);
                  if (!resp.ok) throw new Error(await resp.text());
                  const data: WeeklyItem[] = await resp.json();
                  setWeekly(data);
                } catch (e: any) {
                  setError(e?.message || 'Failed to load weekly earnings');
                } finally {
                  setWeeklyLoading(false);
                }
              }} disabled={weeklyLoading}>
                {weeklyLoading ? 'Loading...' : 'Load This Week'}
              </button>
            </div>
            {weekly.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h3>This Week&apos;s Earnings (sample)</h3>
                <ul>
                  {weekly.map((w) => (
                    <li key={w.ticker} style={{ marginBottom: 12 }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        <strong>{w.ticker}</strong>
                        <span style={{ color: '#555' }}>{w.company}</span>
                        <span style={{ color: '#888' }}>{w.date}</span>
                        <input
                          type="text"
                          placeholder="Paste PDF URL (PR/transcript/10-Q)"
                          value={ingestInputs[w.ticker] || ''}
                          onChange={(e) => setIngestInputs((prev) => ({ ...prev, [w.ticker]: e.target.value }))}
                          style={{ flex: 1, minWidth: 240, padding: 6 }}
                        />
                        <button
                          onClick={async () => {
                            const url = (ingestInputs[w.ticker] || '').trim();
                            if (!url) {
                              setError('Please paste a PDF URL first.');
                              return;
                            }
                            setError('');
                            setIngestingTicker(w.ticker);
                            try {
                              const resp = await fetch(`${API_BASE}/ingest_url`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ url, ticker: w.ticker, company: w.company, filename: undefined }),
                              });
                              if (!resp.ok) throw new Error(await resp.text());
                              const data: UploadResp = await resp.json();
                              setDocId(data.doc_id);
                              // Refresh docs list for this ticker
                              try {
                                setDocsTickerLoading(w.ticker);
                                const r2 = await fetch(`${API_BASE}/docs/list/by_ticker?ticker=${encodeURIComponent(w.ticker)}`);
                                if (r2.ok) {
                                  const list: DocSummary[] = await r2.json();
                                  setDocsByTicker((prev) => ({ ...prev, [w.ticker]: list }));
                                }
                              } catch {}
                              showToast('Ingested PDF', 'success');
                            } catch (e: any) {
                              setError(e?.message || 'Failed to ingest URL');
                              showToast(e?.message || 'Failed to ingest URL', 'error');
                            } finally {
                              setIngestingTicker('');
                              setDocsTickerLoading('');
                            }
                          }}
                          disabled={ingestingTicker === w.ticker}
                        >
                          {ingestingTicker === w.ticker ? 'Ingesting...' : 'Ingest'}
                        </button>
                        <button
                          onClick={async () => {
                            setError('');
                            setIngestingTicker(w.ticker);
                            try {
                              const resp = await fetch(`${API_BASE}/ingest_symbol`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ ticker: w.ticker, prefer: 'edgar' }),
                              });
                              if (!resp.ok) throw new Error(await resp.text());
                              const data: UploadResp = await resp.json();
                              setDocId(data.doc_id);
                              // Refresh docs list for this ticker
                              try {
                                setDocsTickerLoading(w.ticker);
                                const r2 = await fetch(`${API_BASE}/docs/list/by_ticker?ticker=${encodeURIComponent(w.ticker)}`);
                                if (r2.ok) {
                                  const list: DocSummary[] = await r2.json();
                                  setDocsByTicker((prev) => ({ ...prev, [w.ticker]: list }));
                                }
                              } catch {}
                              showToast('Ingested latest document', 'success');
                            } catch (e: any) {
                              setError(e?.message || 'Failed to ingest by symbol');
                              showToast(e?.message || 'Failed to ingest by symbol', 'error');
                            } finally {
                              setIngestingTicker('');
                              setDocsTickerLoading('');
                            }
                          }}
                          disabled={ingestingTicker === w.ticker}
                        >
                          {ingestingTicker === w.ticker ? 'Ingesting...' : 'Ingest Latest'}
                        </button>
                        <button
                          onClick={async () => {
                            setDocsTickerLoading(w.ticker);
                            setError('');
                            try {
                              const resp = await fetch(`${API_BASE}/docs/list/by_ticker?ticker=${encodeURIComponent(w.ticker)}`);
                              if (!resp.ok) throw new Error(await resp.text());
                              const data: DocSummary[] = await resp.json();
                              setDocsByTicker((prev) => ({ ...prev, [w.ticker]: data }));
                            } catch (e: any) {
                              setError(e?.message || 'Failed to load docs for ticker');
                            } finally {
                              setDocsTickerLoading('');
                            }
                          }}
                          disabled={docsTickerLoading === w.ticker}
                        >
                          {docsTickerLoading === w.ticker ? 'Loading Docs...' : 'Docs'}
                        </button>
                        {docId && ingestInputs[w.ticker] && (
                          <span style={{ color: '#0a0' }}>doc_id: <code>{docId}</code> (switch to Ask/Metrics)</span>
                        )}
                      </div>
                      {Array.isArray(docsByTicker[w.ticker]) && docsByTicker[w.ticker]?.length > 0 && (
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                          {docsByTicker[w.ticker]!.map((d) => {
                            const main = d.ticker ? `${d.ticker}${d.company ? ' · ' + d.company : ''}` : (d.filename || `${d.doc_id.slice(0, 8)}…`);
                            const dateStr = d.created_at ? (() => { try { return new Date(d.created_at as string).toLocaleDateString(); } catch { return d.created_at as string; } })() : '';
                            return (
                              <button
                                key={d.doc_id}
                                onClick={() => { setDocId(d.doc_id); try { localStorage.setItem('docId', d.doc_id); } catch {} }}
                                style={{ padding: '6px 10px', border: '1px solid #ddd', borderRadius: 8, background: darkMode ? '#121826' : '#fff', textAlign: 'left' }}
                                title={`${main} • ${d.chunk_count} chunks${dateStr ? ' • ' + dateStr : ''}`}
                              >
                                <div style={{ fontWeight: 600 }}>{main}</div>
                                <div style={{ fontSize: 12, color: darkMode ? '#9fb0c9' : '#666' }}>{d.chunk_count} chunks{dateStr ? ` • ${dateStr}` : ''}</div>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>

      <section style={{ marginTop: 24, padding: 16, border: '1px solid #eee', borderRadius: 8 }}>
        <h2>Health Check</h2>
        <p>
          Backend base: <code>{API_BASE}</code>
        </p>
      </section>

      {/* Toast container */}
      <div style={{ position: 'fixed', right: 16, top: 16, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 60 }}>
        {toasts.map((t) => (
          <div key={t.id} style={{
            padding: '10px 12px', borderRadius: 8, minWidth: 240,
            background: t.type === 'success' ? '#064e3b' : '#7f1d1d', color: '#fff',
            boxShadow: '0 6px 18px rgba(0,0,0,0.25)'
          }}>
            {t.text}
          </div>
        ))}
      </div>

      {/* Persistent Chat Dock */}
      <ChatDock />

      {citationsOpen && (
        <div
          onClick={closeCitations}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 50,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 'min(720px, 92vw)', maxHeight: '80vh', overflow: 'auto',
              background: darkMode ? '#0e1522' : '#fff',
              color: darkMode ? '#eef2f7' : '#000',
              border: '1px solid #ddd', borderRadius: 10, padding: 16,
              boxShadow: '0 10px 30px rgba(0,0,0,0.25)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>Sources</h3>
              <button onClick={closeCitations}>Close</button>
            </div>
            <ul>
              {citationsItems.map((c, i) => (
                <li key={i} style={{ marginBottom: 10, fontSize: 14 }}>
                  <div style={{ color: '#6b7280' }}>
                    [{c.section || 'N/A'}, p.{c.page}]
                  </div>
                  <div>{c.snippet}</div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </main>
  );
}
