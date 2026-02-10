"use client";

import React from "react";

type QuickAction = {
  label: string;
  icon?: React.ReactNode;
  count?: number | null;
  badgeText?: string | null; // e.g., Hot
  onClick?: () => void;
};

type RecentChat = { title: string; subtitle?: string };

type Props = {
  todayCount: number;
  weekCount: number;
  watchlistCount?: number;
  onNewChat?: () => void;
  onGoToday?: () => void;
  onGoThisWeek?: () => void;
  onGoMarketMovers?: () => void;
  onGoWatchlist?: () => void;
};

export default function Sidebar({ todayCount, weekCount, watchlistCount = 0, onNewChat, onGoToday, onGoThisWeek, onGoMarketMovers, onGoWatchlist }: Props) {
  const container: React.CSSProperties = {
    width: 288,
    color: 'var(--sidebar-foreground, var(--color-text))',
    padding: 0,
    position: 'sticky',
    top: 24,
    alignSelf: 'flex-start',
    height: 'calc(100vh - 32px)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  };

  const shellStyle: React.CSSProperties = {
    border: '1px solid var(--sidebar-border, var(--color-border))',
    borderRadius: 20,
    background: 'linear-gradient(180deg, #ffffff, #f8fbff)',
    boxShadow: '0 18px 36px rgba(15,23,42,0.08)',
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    height: '100%',
  };
  const headerStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 };
  const newChatBtn: React.CSSProperties = {
    width: '100%', padding: '11px 14px', borderRadius: 12,
    background: 'linear-gradient(90deg, var(--color-primary), #8b5cf6)',
    color: '#fff', border: 'none', boxShadow: '0 12px 24px rgba(99,102,241,0.35)',
    fontWeight: 600
  };

  const sectionTitle: React.CSSProperties = { fontSize: 11, color: 'var(--color-muted)', margin: '8px 8px 6px', textTransform: 'uppercase', letterSpacing: 0.7, fontWeight: 600 };
  const listStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 6 };

  const itemStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 12px', borderRadius: 12, cursor: 'pointer', transition: 'all .15s ease'
  };
  const left: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 10 };
  const circle = (glyph: string, c: string) => (
    <span
      style={{
        width: 32,
        height: 32,
        borderRadius: 10,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: c,
        color: '#fff',
        fontSize: 16,
        boxShadow: '0 8px 16px rgba(15,23,42,0.2)'
      }}
    >
      {glyph}
    </span>
  );
  const badge = (text: string) => <span style={{ fontSize: 11, color: 'var(--color-primary)', border: '1px solid var(--color-border)', borderRadius: 999, padding: '2px 8px', background: 'rgba(99,102,241,0.08)' }}>{text}</span>;
  const pill = (num: number) => <span style={{ fontSize: 11, background: 'var(--color-surface)', color: 'var(--color-text)', borderRadius: 999, padding: '2px 8px', border: '1px solid var(--color-border)', minWidth: 24, textAlign: 'center' }}>{num}</span>;

  const actions: QuickAction[] = [
    { label: "Today's Earnings", icon: circle('📅', '#3b82f6'), count: todayCount, onClick: onGoToday },
    { label: "This Week", icon: circle('🗓️', '#6366f1'), count: weekCount, onClick: onGoThisWeek },
    { label: "Market Movers", icon: circle('🔥', '#22c55e'), badgeText: 'Hot', onClick: onGoMarketMovers },
    { label: "My Watchlist", icon: circle('⭐', '#f59e0b'), count: watchlistCount, onClick: onGoWatchlist },
  ];

  const recents: RecentChat[] = [
    { title: 'Tech Earnings This Week', subtitle: 'AAPL, GOOGL, MSFT…' },
    { title: 'Healthcare Sector Analysis', subtitle: 'JNJ beat expectations…' },
    { title: 'Q4 Semiconductor Outlook', subtitle: 'NVDA guidance strong…' },
  ];

  const footerTitle: React.CSSProperties = { fontSize: 12, color: 'var(--color-muted)', margin: '0 8px 6px' };
  const footerItemStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 12px',
    borderRadius: 10,
    cursor: 'pointer',
    border: '1px solid transparent',
  };
  const footerItems = [
    { label: 'Bookmarks', icon: '🔖' },
    { label: 'Settings', icon: '⚙️' },
  ];

  return (
    <aside style={container}>
      <div style={shellStyle}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, overflow: 'auto', paddingRight: 6 }}>
          <div>
            <div style={headerStyle}>
              <div style={{ width: 34, height: 34, borderRadius: 10, background: 'linear-gradient(135deg, var(--color-primary), #8b5cf6)' }} />
              <div>
                <div style={{ fontWeight: 700, lineHeight: 1 }}>Earnings Agent</div>
                <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4 }}>Alpha Workspace</div>
              </div>
            </div>
            <button style={newChatBtn} onClick={onNewChat}>+ New Chat</button>
          </div>

          <div>
            <div style={sectionTitle}>Quick Actions</div>
            <div style={listStyle}>
              {actions.map((a, i) => (
                <div
                  key={i}
                  style={{
                    ...itemStyle,
                    background: 'var(--sidebar-accent, var(--color-elevated))',
                    border: '1px solid var(--sidebar-border, var(--color-border))'
                  }}
                  onClick={a.onClick}
                >
                  <div style={left}>
                    {a.icon}
                    <span style={{ fontSize: 14, fontWeight: 500 }}>{a.label}</span>
                  </div>
                  <div>
                    {typeof a.count === 'number' ? pill(a.count) : null}
                    {a.badgeText ? badge(a.badgeText) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div style={sectionTitle}>Recent Chats</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {recents.map((r, i) => (
                <div key={i} style={{ padding: '10px 12px', borderRadius: 12, border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontWeight: 600 }}>{r.title}</div>
                    <span style={{ fontSize: 12, color: 'var(--color-muted)' }}>☆</span>
                  </div>
                  {r.subtitle && <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 2 }}>{r.subtitle}</div>}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ paddingTop: 8, borderTop: '1px solid var(--sidebar-border, var(--color-border))' }}>
          <div style={footerTitle}>Workspace</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {footerItems.map((item) => (
              <div
                key={item.label}
                style={{
                  ...footerItemStyle,
                  background: 'var(--color-surface)',
                  border: '1px solid var(--sidebar-border, var(--color-border))'
                }}
              >
                <span aria-hidden>{item.icon}</span>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}
