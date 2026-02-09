"use client";

import React from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';

type Citation = { section?: string | null; page: number; snippet: string };

type AnswerBullet = { text: string; citations: Citation[] };

type QueryResp = { bullets: AnswerBullet[]; chart?: { labels?: string[]; values?: number[] } };

export default function ChatDock() {
  const [open, setOpen] = React.useState<boolean>(() => {
    try { return localStorage.getItem('chatDockOpen') === 'true'; } catch { return false; }
  });
  const [docId, setDocId] = React.useState<string>("");
  const [input, setInput] = React.useState<string>("");
  const [sending, setSending] = React.useState(false);
  const [history, setHistory] = React.useState<{ q: string, a: AnswerBullet[] }[]>([]);
  const [error, setError] = React.useState<string>("");

  React.useEffect(() => {
    try {
      const saved = localStorage.getItem('docId');
      if (saved) setDocId(saved);
    } catch {}
  }, []);

  React.useEffect(() => {
    try { localStorage.setItem('chatDockOpen', String(open)); } catch {}
  }, [open]);

  // Allow other components to open/close the dock via custom events
  React.useEffect(() => {
    const onOpen = () => setOpen(true);
    const onClose = () => setOpen(false);
    if (typeof window !== 'undefined') {
      window.addEventListener('openChatDock', onOpen);
      window.addEventListener('closeChatDock', onClose);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('openChatDock', onOpen);
        window.removeEventListener('closeChatDock', onClose);
      }
    };
  }, []);

  const onSend = async () => {
    if (!docId || !input.trim()) return;
    setSending(true);
    setError("");
    const q = input.trim();
    setInput("");
    try {
      const resp = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId, question: q })
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

  const btnStyle: React.CSSProperties = {
    position: 'fixed', right: 16, bottom: 16, zIndex: 70,
    background: 'var(--color-primary)', color: 'var(--color-primary-contrast)', borderRadius: 999, border: 'none',
    padding: '10px 14px', boxShadow: 'var(--shadow-1)', cursor: 'pointer'
  };
  const panelStyle: React.CSSProperties = {
    position: 'fixed', right: 16, bottom: 70, width: 'min(420px, 92vw)',
    background: 'var(--color-surface)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 12,
    boxShadow: 'var(--shadow-2)', zIndex: 70, overflow: 'hidden'
  };

  return (
    <>
      {!open && (
        <button style={btnStyle} onClick={() => setOpen(true)}>Chat ▸</button>
      )}
      {open && (
        <div style={panelStyle}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 12, borderBottom: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600 }}>Chat</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>{docId ? `doc: ${docId.slice(0,8)}…` : 'no context'}</div>
              <button onClick={() => setOpen(false)} style={{ border: '1px solid var(--color-border)', background: 'var(--color-elevated)', color: 'var(--color-text)', borderRadius: 8, padding: '4px 8px' }}>Close</button>
            </div>
          </div>
          <div style={{ maxHeight: 280, overflow: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {!docId && (
              <div style={{ color: 'var(--danger-text)' }}>No context selected. Open a ticker’s Detail and click “Set context”, or select a document on Home.</div>
            )}
            {history.map((h, idx) => (
              <div key={idx}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Q: {h.q}</div>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {h.a.map((b, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>{b.text}</li>
                  ))}
                </ul>
              </div>
            ))}
            {history.length === 0 && (
              <div style={{ color: 'var(--color-muted)' }}>Try: “What changed in guidance?” or “Summarize the quarter in 3 bullets.”</div>
            )}
            {error && <div style={{ color: 'var(--danger-text)' }}>{error}</div>}
          </div>
          <div style={{ borderTop: '1px solid var(--color-border)', padding: 10, display: 'flex', gap: 8 }}>
            <input
              type="text"
              placeholder={docId ? 'Ask a question…' : 'Select context first (Set context)'}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!docId || sending}
              style={{ flex: 1, padding: 8, borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-elevated)', color: 'var(--color-text)' }}
            />
            <button onClick={onSend} disabled={!docId || sending || !input.trim()} style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)', borderRadius: 8, padding: '8px 12px', border: 'none' }}>{sending ? 'Sending…' : 'Send'}</button>
          </div>
        </div>
      )}
    </>
  );
}
