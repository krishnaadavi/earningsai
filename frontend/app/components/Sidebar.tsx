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
    width: 260,
    borderRight: '1px solid var(--sidebar-border, var(--color-border))',
    background: 'var(--sidebar, var(--color-bg))',
    color: 'var(--sidebar-foreground, var(--color-text))',
    padding: 16,
    position: 'sticky',
    top: 56, // below header
    alignSelf: 'flex-start',
    height: 'calc(100vh - 56px)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  };

  const headerStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 };
  const newChatBtn: React.CSSProperties = {
    width: '100%', padding: '10px 12px', borderRadius: 10,
    background: 'linear-gradient(90deg, var(--color-primary), #8b5cf6)',
    color: '#fff', border: 'none', boxShadow: 'var(--shadow-1)'
  };

  const sectionTitle: React.CSSProperties = { fontSize: 12, color: 'var(--color-muted)', margin: '14px 8px 8px' };
  const listStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 6 };

  const itemStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 12px', borderRadius: 12, cursor: 'pointer',
  };
  const left: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 10 };
  const circle = (glyph: string, c: string) => (
    <span
      style={{
        width: 32,
        height: 32,
        borderRadius: 12,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: c,
        color: '#fff',
        fontSize: 16,
        boxShadow: '0 10px 18px rgba(99,102,241,0.16)'
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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, overflow: 'auto', paddingRight: 6 }}>
        <div>
          <div style={headerStyle}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, var(--color-primary), #8b5cf6)' }} />
            <div style={{ fontWeight: 700 }}>Earnings Agent</div>
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
                  <span>{a.label}</span>
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
              <div key={i} style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}>
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
    </aside>
  );
}
