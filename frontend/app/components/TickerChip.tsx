"use client";

import React from "react";

type Props = {
  ticker: string;
  company?: string | null;
  tags?: string[];
  onClick?: () => void;
  watchlisted?: boolean;
  onToggleWatchlist?: () => void;
  onSetContext?: () => void;
};

export default function TickerChip({ ticker, company, tags = [], onClick, watchlisted = false, onToggleWatchlist, onSetContext }: Props) {
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 10px',
    borderRadius: 999,
    background: 'var(--color-elevated)',
    color: 'var(--color-text)',
    border: '1px solid var(--color-border)',
  };
  const tagStyle = (t: string): React.CSSProperties => {
    const tl = (t || '').toLowerCase();
    let bg = 'var(--chip-tag-bg)';
    let bd = 'var(--chip-tag-border)';
    let fg = 'var(--chip-tag-text)';
    if (tl.includes('beat')) { bg = 'var(--success-bg)'; bd = 'var(--success-border)'; fg = 'var(--success-text)'; }
    if (tl.includes('miss')) { bg = 'var(--danger-bg)'; bd = 'var(--danger-border)'; fg = 'var(--danger-text)'; }
    if (tl.startsWith('up')) { bg = 'var(--success-bg)'; bd = 'var(--success-border)'; fg = 'var(--success-text)'; }
    if (tl.startsWith('down')) { bg = 'var(--danger-bg)'; bd = 'var(--danger-border)'; fg = 'var(--danger-text)'; }
    return {
      fontSize: 10,
      padding: '2px 6px',
      borderRadius: 999,
      border: `1px solid ${bd}`,
      background: bg,
      color: fg,
    };
  };
  const starBtn: React.CSSProperties = {
    background: 'transparent', border: 'none', color: watchlisted ? 'var(--warning)' : 'var(--color-muted)',
    fontSize: 14, padding: 0, marginLeft: 2, cursor: 'pointer'
  };
  const ctxBtn: React.CSSProperties = {
    background: 'transparent', border: '1px solid var(--color-border)', color: 'var(--color-text)',
    fontSize: 10, padding: '2px 6px', marginLeft: 6, borderRadius: 999, cursor: 'pointer'
  };
  return (
    <button onClick={onClick} style={baseStyle}>
      <span style={{ fontWeight: 600, fontSize: 12 }}>{ticker}</span>
      {company && <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>{company}</span>}
      <span style={{ display: 'flex', gap: 6 }}>
        {tags.map((t, i) => (
          <span key={i} style={tagStyle(t)}>{t}</span>
        ))}
      </span>
      {onToggleWatchlist && (
        <span>
          <button
            aria-label={watchlisted ? 'Remove from watchlist' : 'Add to watchlist'}
            title={watchlisted ? 'Remove from watchlist' : 'Add to watchlist'}
            onClick={(e) => { e.stopPropagation(); onToggleWatchlist?.(); }}
            style={starBtn}
          >{watchlisted ? '★' : '☆'}</button>
        </span>
      )}
      {onSetContext && (
        <span>
          <button
            aria-label="Set context"
            title="Set context"
            onClick={(e) => { e.stopPropagation(); onSetContext?.(); }}
            style={ctxBtn}
          >Set</button>
        </span>
      )}
    </button>
  );
}
