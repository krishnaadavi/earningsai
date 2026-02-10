"use client";

import React from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';

type Citation = { section?: string | null; page: number; snippet: string };

type AnswerBullet = { text: string; citations: Citation[] };

type QueryResp = { bullets: AnswerBullet[] };

type Props = {
  onClose?: () => void;
};

const BASE_SUGGESTIONS: { text: string; icon: string; color: string }[] = [
  { text: "Show me today's daily highlights", icon: "✨", color: "#6366f1" },
  { text: "Show me this week's earnings", icon: "🗓️", color: "#8b5cf6" },
  { text: "Show me today's earnings summaries", icon: "🧾", color: "#0ea5e9" },
  { text: "What are today's most important earnings?", icon: "📈", color: "#22c55e" },
  { text: "Which healthcare stocks report next?", icon: "💊", color: "#06b6d4" },
  { text: "Show me pre-market earnings movers", icon: "🚀", color: "#f97316" },
];

type GuidanceEntry = {
  id?: string;
  metric?: string | null;
  period?: string | null;
  value_low?: number | null;
  value_high?: number | null;
  value_point?: number | null;
  unit?: string | null;
  outlook_note?: string | null;
  confidence?: string | null;
  citations?: { section?: string | null; page?: number; snippet: string }[];
};

export default function ChatPanel({ onClose }: Props) {
  const [docId, setDocId] = React.useState<string>("");
  const [pendingDocId, setPendingDocId] = React.useState<string>("");
  const [input, setInput] = React.useState<string>("");
  const [sending, setSending] = React.useState(false);
  const [history, setHistory] = React.useState<{ q: string, a: AnswerBullet[] }[]>([]);
  const [error, setError] = React.useState<string>("");
  const [isDark, setIsDark] = React.useState(false);
  const [hoveredSuggestion, setHoveredSuggestion] = React.useState<number | null>(null);
  const [docMeta, setDocMeta] = React.useState<{ ticker?: string | null; company?: string | null } | null>(null);
  const [contextMetrics, setContextMetrics] = React.useState<Record<string, { value: number; unit?: string; period?: string | null }>>({});
  const [contextLoading, setContextLoading] = React.useState(false);
  const [contextGuidance, setContextGuidance] = React.useState<GuidanceEntry[]>([]);

  React.useEffect(() => {
    if (typeof document === 'undefined') return;
    const update = () => setIsDark(document.documentElement.classList.contains('dark'));
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  React.useEffect(() => {
    try {
      const saved = localStorage.getItem('docId');
      if (saved) setDocId(saved);
    } catch {}
  }, []);

  React.useEffect(() => {
    setPendingDocId(docId || "");
  }, [docId]);

  React.useEffect(() => {
    if (!docId) {
      setDocMeta(null);
      setContextMetrics({});
      setContextGuidance([]);
      return;
    }
    let aborted = false;

    const normalizeGuidance = (raw: any): GuidanceEntry[] => {
      if (!raw) return [];
      const arr = Array.isArray(raw)
        ? raw
        : Array.isArray(raw?.guidance)
          ? raw.guidance
          : [];
      const toNumber = (val: any): number | null => {
        if (val === null || val === undefined) return null;
        const num = typeof val === 'number' ? val : Number(val);
        return Number.isFinite(num) ? num : null;
      };
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
              } as GuidanceEntry;
            }
            return {
              metric: typeof item.metric === 'string' ? item.metric : null,
              period: typeof item.period === 'string' ? item.period : null,
              value_low: toNumber(item.value_low),
              value_high: toNumber(item.value_high),
              value_point: toNumber(item.value_point),
              unit: typeof item.unit === 'string' ? item.unit : null,
              outlook_note: typeof item.outlook_note === 'string' ? item.outlook_note : null,
              confidence: typeof item.confidence === 'string' ? item.confidence : null,
              citations: Array.isArray(item.citations) ? item.citations : [],
            } as GuidanceEntry;
          }
          return null;
        })
        .filter(Boolean) as GuidanceEntry[];
    };

    const loadContext = async () => {
      setContextLoading(true);
      try {
        const metaResp = await fetch(`${API_BASE}/docs/${encodeURIComponent(docId)}`);
        if (metaResp.ok) {
          const meta = await metaResp.json();
          if (!aborted) setDocMeta(meta || null);
        }
        const metricsResp = await fetch(`${API_BASE}/metrics`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doc_id: docId }),
        });
        if (metricsResp.ok) {
          const data = await metricsResp.json();
          if (!aborted) setContextMetrics(data.metrics || {});
        }
        const guidanceResp = await fetch(`${API_BASE}/guidance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doc_id: docId }),
        });
        if (guidanceResp.ok) {
          const payload = await guidanceResp.json();
          if (!aborted) {
            setContextGuidance(normalizeGuidance(payload).slice(0, 6));
          }
        } else if (!aborted) {
          setContextGuidance([]);
        }
      } catch (e: any) {
        if (!aborted) setError((prev) => prev || e?.message || 'Failed to load context');
      } finally {
        if (!aborted) setContextLoading(false);
      }
    };
    loadContext();
    return () => { aborted = true; };
  }, [docId]);

  const ask = async (question: string) => {
    if (!question.trim()) return;
    const q = question.trim();
    setInput("");
    setSending(true);
    setError("");
    try {
      const resp = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId || undefined, question: q })
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data: QueryResp = await resp.json();
      setHistory((h) => [...h, { q, a: data.bullets || [] }]);
    } catch (e: any) {
      setError(e?.message || 'Query failed');
    } finally {
      setSending(false);
    }
  };

  const setContextDocId = () => {
    const v = (pendingDocId || "").trim();
    if (!v) return;
    try {
      localStorage.setItem('docId', v);
    } catch {}
    setDocId(v);
  };

  const clearContextDocId = () => {
    try {
      localStorage.removeItem('docId');
    } catch {}
    setDocId("");
    setPendingDocId("");
  };

  const onSend = async () => ask(input);

  const contextSuggestions = React.useMemo(() => {
    if (!docMeta?.ticker) return [] as { text: string; icon: string; color: string }[];
    const ticker = (docMeta.ticker || '').toUpperCase();
    return [
      { text: `Summarize ${ticker}'s forward guidance`, icon: "🎯", color: "#f59e0b" },
      { text: `What drove ${ticker}'s revenue last quarter?`, icon: "💹", color: "#10b981" },
      { text: `Compare ${ticker}'s capex vs. prior quarter`, icon: "🏗️", color: "#6366f1" },
      ...(contextGuidance.length > 0 ? [{ text: `What does management expect next quarter for ${ticker}?`, icon: "🧭", color: "#0ea5e9" }] : []),
    ];
  }, [docMeta, contextGuidance.length]);

  const suggestions = React.useMemo(() => {
    return docMeta?.ticker ? [...contextSuggestions, ...BASE_SUGGESTIONS] : BASE_SUGGESTIONS;
  }, [contextSuggestions, docMeta]);

  const card: React.CSSProperties = {
    background: isDark
      ? 'linear-gradient(180deg, rgba(17,24,39,0.92), rgba(9,12,21,0.96))'
      : 'linear-gradient(180deg, #ffffff, #f8fbff)',
    border: '1px solid var(--color-border)',
    borderRadius: 20,
    padding: 28,
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
    boxShadow: isDark ? '0 26px 42px rgba(0,0,0,0.35)' : '0 20px 40px rgba(15, 23, 42, 0.10)'
  };
  const hero: React.CSSProperties = { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center' };
  const heroIcon: React.CSSProperties = {
    width: 64,
    height: 64,
    borderRadius: 20,
    background: 'linear-gradient(135deg, var(--color-primary), #8b5cf6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--color-primary-contrast)',
    fontSize: 28,
    boxShadow: '0 18px 36px rgba(99,102,241,0.25)'
  };
  const statusPill: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    borderRadius: 999,
    padding: '4px 10px',
    border: '1px solid var(--color-border)',
    background: isDark ? 'rgba(148,163,184,0.14)' : 'var(--color-elevated)',
    fontSize: 12,
    color: 'var(--color-muted)'
  };
  const statusDot = (on: boolean): React.CSSProperties => ({
    width: 8,
    height: 8,
    borderRadius: 999,
    background: on ? '#22c55e' : '#9ca3af',
    boxShadow: on ? '0 0 0 4px rgba(34,197,94,0.15)' : 'none'
  });
  const suggestionGrid: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 12
  };
  const suggestionButton: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    padding: '14px 16px',
    borderRadius: 14,
    border: '1px solid var(--color-border)',
    background: isDark ? 'rgba(30,41,59,0.72)' : 'var(--color-elevated)',
    color: 'var(--color-text)',
    fontSize: 14,
    textAlign: 'left',
    cursor: 'pointer',
    transition: 'transform 0.15s ease, box-shadow 0.15s ease'
  };
  const suggestionButtonHover: React.CSSProperties = {
    transform: 'translateY(-2px)',
    boxShadow: '0 14px 24px rgba(15,23,42,0.08)'
  };
  const suggestionIcon = (bg: string): React.CSSProperties => ({
    width: 32,
    height: 32,
    borderRadius: 12,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: bg,
    color: '#fff',
    fontSize: 16
  });
  const footNote: React.CSSProperties = { fontSize: 13, color: 'var(--color-muted)', textAlign: 'center' };
  const inputRow: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 12 };
  const inputStyle: React.CSSProperties = {
    flex: 1,
    padding: '12px 16px',
    borderRadius: 14,
    border: '1px solid var(--color-border)',
    background: isDark ? 'rgba(15,23,42,0.62)' : 'var(--color-surface)',
    color: 'var(--color-text)',
    fontSize: 14
  };
  const sendButton: React.CSSProperties = {
    background: 'linear-gradient(90deg, var(--color-primary), #8b5cf6)',
    color: 'var(--color-primary-contrast)',
    borderRadius: 14,
    padding: '12px 18px',
    border: 'none',
    fontWeight: 600,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8
  };
  const historyCard = (dark: boolean): React.CSSProperties => ({
    border: '1px solid var(--color-border)',
    borderRadius: 14,
    padding: 14,
    background: dark ? 'rgba(15,23,42,0.35)' : 'var(--color-surface)'
  });

  return (
    <section style={card}>
      <div style={{ position: 'relative' }}>
        {onClose && (
          <button
            onClick={onClose}
            style={{ position: 'absolute', top: 0, right: 0, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', borderRadius: 999, padding: '6px 12px', fontSize: 12 }}
          >
            Close
          </button>
        )}
        <div style={hero}>
          <div style={heroIcon}>✨</div>
          <div>
            <h2 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>Welcome to Earnings Agent</h2>
            <p style={{ margin: '8px 0 0', fontSize: 14, color: 'var(--color-muted)' }}>
              Your AI assistant for earnings analysis, market insights, and trading intelligence. Ask about upcoming earnings, company analysis, or market trends.
            </p>
          </div>
          <span style={statusPill}>
            <span style={statusDot(true)} aria-hidden />
            Online
          </span>
        </div>
      </div>

      <div style={suggestionGrid}>
        {suggestions.map((s, i) => {
          const hover = hoveredSuggestion === i ? suggestionButtonHover : {};
          return (
            <button
              key={i}
              style={{ ...suggestionButton, ...hover }}
              onClick={() => ask(s.text)}
              onMouseEnter={() => setHoveredSuggestion(i)}
              onMouseLeave={() => setHoveredSuggestion(null)}
              onBlur={() => setHoveredSuggestion((prev) => (prev === i ? null : prev))}
              aria-label={s.text}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={suggestionIcon(s.color)} aria-hidden>{s.icon}</span>
                {s.text}
              </span>
              <span aria-hidden style={{ color: 'var(--color-muted)' }}>↗</span>
            </button>
          );
        })}
      </div>

      <div style={footNote}>Ask about earnings, companies, or market trends.</div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--color-muted)', flexWrap: 'wrap' }}>
        <span>Context:</span>
        <span style={{ border: '1px solid var(--color-border)', borderRadius: 999, padding: '2px 10px', background: 'var(--color-elevated)', color: 'var(--color-text)' }}>
          {docMeta?.ticker ? `${docMeta.ticker.toUpperCase()}${docMeta?.company ? ` · ${docMeta.company}` : ''}` : docId ? `doc ${docId.slice(0, 8)}…` : 'none'}
        </span>
        <span style={{ marginLeft: 8, color: 'var(--color-muted)' }}>|</span>
        <input
          type="text"
          placeholder="doc_id"
          value={pendingDocId}
          onChange={(e) => setPendingDocId(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') setContextDocId(); }}
          style={{ padding: '6px 10px', borderRadius: 10, border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12, minWidth: 220 }}
        />
        <button
          onClick={setContextDocId}
          disabled={!pendingDocId.trim()}
          style={{ border: '1px solid var(--color-border)', borderRadius: 10, padding: '6px 10px', background: 'var(--color-elevated)', color: 'var(--color-text)', fontSize: 12, opacity: !pendingDocId.trim() ? 0.6 : 1 }}
        >
          Set
        </button>
        {docId && (
          <button
            onClick={clearContextDocId}
            style={{ border: '1px solid var(--color-border)', borderRadius: 10, padding: '6px 10px', background: 'var(--color-elevated)', color: 'var(--color-text)', fontSize: 12 }}
          >
            Clear
          </button>
        )}
      </div>

      {docId && (
        <div style={{ border: '1px solid var(--color-border)', borderRadius: 12, padding: 14, background: 'var(--color-elevated)', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 600, color: 'var(--color-text)' }}>Context snapshot</div>
            {contextLoading && <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>Loading…</div>}
          </div>
          {Object.keys(contextMetrics || {}).length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>No metrics yet for this document.</div>
          ) : (
            <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
              {Object.entries(contextMetrics)
                .sort(([a], [b]) => a.localeCompare(b))
                .slice(0, 4)
                .map(([key, item]) => {
                  const val = item?.value;
                  const formatted = (() => {
                    if (typeof val !== 'number') return '—';
                    if (Math.abs(val) >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(2)}B`;
                    if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`;
                    if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
                    return val.toFixed(2);
                  })();
                  return (
                    <div key={key} style={{ borderRadius: 10, border: '1px solid var(--color-border)', background: 'var(--color-surface)', padding: 10 }}>
                      <div style={{ fontSize: 11, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{key.replace(/_/g, ' ')}</div>
                      <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-text)' }}>{formatted}{item?.unit ? ` ${item.unit}` : ''}</div>
                      {item?.period && <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>{item.period}</div>}
                    </div>
                  );
                })}
            </div>
          )}
          {contextGuidance.length > 0 && (
            <div style={{ border: '1px solid var(--color-border)', borderRadius: 10, padding: 12, background: 'var(--color-surface)', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Forward guidance</div>
              <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {contextGuidance.map((entry, idx) => {
                  const labelParts = [
                    entry.metric ? entry.metric.toUpperCase() : null,
                    entry.period || null
                  ].filter(Boolean);
                  const heading = labelParts.join(' · ') || 'Guidance';
                  const formatNumber = (val: number | null | undefined) => {
                    if (val === null || val === undefined) return null;
                    const abs = Math.abs(val);
                    if (abs >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(2)}B`;
                    if (abs >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`;
                    if (abs >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
                    return val.toFixed(2);
                  };
                  const rangeParts: string[] = [];
                  if (entry.value_low != null || entry.value_high != null) {
                    const low = formatNumber(entry.value_low ?? null);
                    const high = formatNumber(entry.value_high ?? null);
                    if (low && high) {
                      rangeParts.push(`${low} – ${high}`);
                    } else if (low) {
                      rangeParts.push(low);
                    } else if (high) {
                      rangeParts.push(high);
                    }
                  }
                  if (entry.value_point != null && rangeParts.length === 0) {
                    const point = formatNumber(entry.value_point);
                    if (point) rangeParts.push(point);
                  }
                  const rangeText = rangeParts.length > 0
                    ? `${rangeParts.join(' to ')}${entry.unit ? ` ${entry.unit}` : ''}`
                    : null;
                  return (
                    <li key={idx} style={{ color: 'var(--color-text)' }}>
                      <div style={{ fontWeight: 600 }}>{heading}</div>
                      {rangeText && <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>{rangeText}</div>}
                      {entry.outlook_note && <div style={{ fontSize: 12 }}>{entry.outlook_note}</div>}
                      {entry.confidence && <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>Confidence: {entry.confidence}</div>}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 260, overflow: 'auto' }}>
        {history.map((h, idx) => (
          <div key={idx} style={historyCard(isDark)}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>Q: {h.q}</div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {h.a.map((b, i) => (
                <li key={i} style={{ marginBottom: 4 }}>{b.text}</li>
              ))}
            </ul>
          </div>
        ))}
        {history.length === 0 && (
          <div style={{ color: 'var(--color-muted)', textAlign: 'center', padding: 16, border: '1px dashed var(--color-border)', borderRadius: 12 }}>
            Try a quick action above or ask your own question below.
          </div>
        )}
        {error && <div style={{ color: 'var(--danger-text)' }}>{error}</div>}
      </div>

      <div style={inputRow}>
        <input
          type="text"
          placeholder={docId ? 'Ask a question…' : 'Optional: set context via a highlight → Set context'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          disabled={sending}
          style={inputStyle}
        />
        <button
          onClick={onSend}
          disabled={sending || !input.trim()}
          style={{
            ...sendButton,
            opacity: sending || !input.trim() ? 0.7 : 1,
            cursor: sending || !input.trim() ? 'not-allowed' : 'pointer'
          }}
        >
          {sending ? 'Sending…' : 'Send'}
        </button>
      </div>
    </section>
  );
}
