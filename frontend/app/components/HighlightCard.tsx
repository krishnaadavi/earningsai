"use client";

import React from "react";

type Props = {
  ticker: string;
  company?: string | null;
  summary: any;
  rankScore?: number | null;
  onOpen?: () => void;
  onSetContextTicker?: () => void;
};

export default function HighlightCard({ ticker, company, summary, rankScore, onOpen, onSetContextTicker }: Props) {
  const bullets: string[] = Array.isArray(summary?.bullets) ? summary.bullets : [];
  const rank = typeof rankScore === 'number' ? rankScore : (typeof summary?.rank_score === 'number' ? summary.rank_score : undefined);

  const cardStyle: React.CSSProperties = {
    borderRadius: 12,
    border: '1px solid var(--color-border)',
    background: 'var(--color-surface)',
    color: 'var(--color-text)',
    padding: 16,
    width: '100%'
  };
  const headerStyle: React.CSSProperties = { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 };
  const titleStyle: React.CSSProperties = { fontSize: 18, fontWeight: 600 };
  const scoreStyle: React.CSSProperties = { fontSize: 12, color: 'var(--color-muted)' };
  const bulletsStyle: React.CSSProperties = { marginTop: 8, fontSize: 14, color: 'var(--color-text)' };
  const emptyStyle: React.CSSProperties = { marginTop: 8, fontSize: 14, color: 'var(--color-muted)' };
  const btnStyle: React.CSSProperties = { marginTop: 12, padding: '6px 10px', fontSize: 14, borderRadius: 8, background: 'var(--color-primary)', color: 'var(--color-primary-contrast)', border: 'none' };
  const secondaryBtn: React.CSSProperties = { marginTop: 12, padding: '6px 10px', fontSize: 14, borderRadius: 8, background: 'var(--color-elevated)', color: 'var(--color-text)', border: '1px solid var(--color-border)' };

  return (
    <div style={cardStyle}>
      <div style={headerStyle}>
        <div style={titleStyle}>{ticker}{company ? ` · ${company}` : ''}</div>
        {typeof rank === 'number' && (
          <div style={scoreStyle}>score: {rank.toFixed(2)}</div>
        )}
      </div>
      {bullets.length > 0 ? (
        <ul style={bulletsStyle}>
          {bullets.slice(0, 3).map((b, i) => (
            <li key={i} style={{ listStyle: 'disc', marginLeft: 16 }}>{b}</li>
          ))}
        </ul>
      ) : (
        <div style={emptyStyle}>No bullets yet</div>
      )}
      <div>
        <button onClick={onOpen} style={btnStyle}>See details</button>
        {onSetContextTicker && (
          <button onClick={onSetContextTicker} style={{ ...secondaryBtn, marginLeft: 8 }}>Set context</button>
        )}
      </div>
    </div>
  );
}
