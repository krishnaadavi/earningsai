"use client";

import React from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';

export default function IngestionPage() {
  const [loading, setLoading] = React.useState(false);
  const [items, setItems] = React.useState<any[]>([]);
  const [error, setError] = React.useState<string>("");
  const [jobFilter, setJobFilter] = React.useState<'all' | 'ingest_today' | 'refresh_next_14_days'>("all");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(`${API_BASE}/metrics/ingestion/recent?limit=50`);
      if (!r.ok) throw new Error(await r.text());
      const j = await r.json();
      const arr = Array.isArray(j?.items) ? j.items : [];
      setItems(arr);
    } catch (e: any) {
      setError(e?.message || 'Failed to load ingestion metrics');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const filtered = React.useMemo(() => {
    if (jobFilter === 'all') return items;
    return (items || []).filter((x) => x.job_type === jobFilter);
  }, [items, jobFilter]);

  const pageStyle: React.CSSProperties = {
    maxWidth: 1100, margin: '24px auto', padding: '0 16px',
    fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto', color: 'var(--color-text)'
  };
  const card: React.CSSProperties = { background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 16 };
  const head: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 };
  const btn: React.CSSProperties = { padding: '6px 10px', borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-elevated)', color: 'var(--color-text)' };
  const th: React.CSSProperties = { textAlign: 'left', fontSize: 12, color: 'var(--color-muted)', padding: '8px 6px', borderBottom: '1px solid var(--color-border)' };
  const td: React.CSSProperties = { fontSize: 13, padding: '10px 6px', borderBottom: '1px solid var(--color-border)' };

  return (
    <main style={pageStyle}>
      <h1 style={{ marginBottom: 8 }}>Ingestion Metrics</h1>
      <div style={{ color: 'var(--color-muted)', marginBottom: 16 }}>Backend base: <code>{API_BASE}</code></div>

      <section style={card}>
        <div style={head}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <strong>Recent Runs</strong>
            <select
              value={jobFilter}
              onChange={(e) => setJobFilter(e.target.value as any)}
              style={{ ...btn, padding: '6px 8px' }}
            >
              <option value="all">All</option>
              <option value="ingest_today">ingest_today</option>
              <option value="refresh_next_14_days">refresh_next_14_days</option>
            </select>
          </div>
          <button onClick={load} style={btn} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        {error && <div style={{ color: 'tomato', marginBottom: 8 }}>{error}</div>}

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={th}>Time</th>
                <th style={th}>Job</th>
                <th style={th}>Requested</th>
                <th style={th}>Success</th>
                <th style={th}>Errors</th>
                <th style={th}>Details</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id}>
                  <td style={td}>{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</td>
                  <td style={td}>{r.job_type}</td>
                  <td style={td}>{r.requested ?? r.count ?? '—'}</td>
                  <td style={td}>{r.success ?? r.count ?? '—'}</td>
                  <td style={td}>{r.error_count ?? 0}</td>
                  <td style={td}>
                    {r.job_type === 'ingest_today' ? (
                      <span title={(r.tickers || []).join(', ')}>
                        {(r.tickers || []).slice(0, 8).join(', ')}{(r.tickers || []).length > 8 ? ` +${(r.tickers || []).length - 8}` : ''}
                      </span>
                    ) : r.job_type === 'refresh_next_14_days' ? (
                      <span>
                        {r.range?.start} → {r.range?.end} ({r.count ?? '—'})
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td style={td} colSpan={6}>
                    <span style={{ color: 'var(--color-muted)' }}>No runs yet.</span>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
