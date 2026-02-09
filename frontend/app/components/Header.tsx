"use client";

import React from "react";

export default function Header() {
  const [dark, setDark] = React.useState(false);

  // Initialize from localStorage or system preference
  React.useEffect(() => {
    try {
      const saved = localStorage.getItem('theme');
      const prefers = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const isDark = saved ? saved === 'dark' : !!prefers;
      setDark(isDark);
      if (typeof document !== 'undefined') {
        document.documentElement.classList.toggle('dark', isDark);
      }
    } catch {}
  }, []);

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    try { localStorage.setItem('theme', next ? 'dark' : 'light'); } catch {}
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('dark', next);
    }
  };

  const headerStyle: React.CSSProperties = {
    position: 'sticky', top: 0, zIndex: 40,
    background: 'linear-gradient(90deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08))',
    color: 'var(--color-text)',
    borderBottom: '1px solid var(--color-border)',
    backdropFilter: 'blur(16px)'
  };
  const navStyle: React.CSSProperties = {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '12px 20px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16
  };
  const brandStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 12
  };
  const logoStyle: React.CSSProperties = {
    width: 36,
    height: 36,
    borderRadius: 12,
    background: 'linear-gradient(135deg, var(--color-primary), #8b5cf6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--color-primary-contrast)',
    fontWeight: 700,
    fontSize: 18
  };
  const statusDot = (on: boolean): React.CSSProperties => ({
    width: 10,
    height: 10,
    borderRadius: 999,
    background: on ? '#16a34a' : '#9ca3af',
    boxShadow: on ? '0 0 0 4px rgba(22,163,74,0.18)' : 'none'
  });
  const actionRow: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 12
  };
  const googleBtn: React.CSSProperties = {
    borderRadius: 999,
    padding: '8px 14px',
    border: '1px solid var(--color-border)',
    background: 'var(--color-surface)',
    color: 'var(--color-text)',
    fontSize: 13,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    opacity: 0.7,
    cursor: 'not-allowed'
  };
  const toggleStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    border: '1px solid var(--color-border)',
    borderRadius: 999,
    padding: '4px 8px',
    background: 'var(--color-elevated)',
    color: 'var(--color-text)'
  };

  return (
    <header style={headerStyle}>
      <nav style={navStyle}>
        <div style={brandStyle}>
          <div style={logoStyle}>EA</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <a href="/" style={{ color: 'inherit', textDecoration: 'none', fontWeight: 700 }}>Earnings Agent</a>
              <span style={{ fontSize: 11, border: '1px solid var(--color-border)', borderRadius: 999, padding: '2px 8px', color: 'var(--color-muted)' }}>Alpha</span>
            </div>
            <span style={{ fontSize: 12, color: 'var(--color-muted)' }}>Cutting Edge Insights from earnings calls & Market Moves</span>
          </div>
        </div>
        <div style={actionRow}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-muted)' }}>
            <span style={statusDot(true)} aria-hidden />
            <span>Online</span>
          </div>
          <button style={googleBtn} aria-disabled title="Google sign-in coming soon">
            <span aria-hidden>🔒</span>
            <span>Sign in with Google</span>
          </button>
          <button onClick={toggleDark} style={toggleStyle} aria-label="Toggle dark mode">
            <span style={statusDot(dark)} />
            <span style={{ fontSize: 12 }}>{dark ? 'Dark' : 'Light'}</span>
          </button>
        </div>
      </nav>
    </header>
  );
}
