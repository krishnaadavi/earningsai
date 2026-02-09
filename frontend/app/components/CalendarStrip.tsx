"use client";

import React from "react";

type Event = {
  id: string;
  ticker: string;
  company?: string | null;
  event_date: string; // ISO
  time_of_day?: string | null; // BMO/AMC
  status?: string | null;
};

type Props = {
  weekStart: Date; // Monday of week
  events: Event[];
  selectedDate: Date;
  onSelectDate: (d: Date) => void;
};

export default function CalendarStrip({ weekStart, events, selectedDate, onSelectDate }: Props) {
  // Build Mon..Fri
  const days: Date[] = React.useMemo(() => {
    const out: Date[] = [];
    for (let i = 0; i < 5; i++) {
      const d = new Date(weekStart);
      d.setDate(weekStart.getDate() + i);
      out.push(d);
    }
    return out;
  }, [weekStart]);

  const fmt = (d: Date) => d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  const iso = (d: Date) => d.toISOString().split('T')[0];

  const counts: Record<string, number> = React.useMemo(() => {
    const m: Record<string, number> = {};
    for (const ev of events || []) {
      const dd = new Date(ev.event_date);
      const key = iso(dd);
      m[key] = (m[key] || 0) + 1;
    }
    return m;
  }, [events]);

  const container: React.CSSProperties = {
    display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap'
  };
  const dayStyle = (d: Date): React.CSSProperties => {
    const key = iso(d);
    const isSel = iso(selectedDate) === key;
    return {
      padding: '8px 10px', border: '1px solid var(--color-border)', borderRadius: 8,
      background: isSel ? 'var(--color-selection)' : 'var(--color-elevated)', color: 'var(--color-text)',
      minWidth: 80, textAlign: 'center', cursor: 'pointer'
    };
  };
  const countStyle: React.CSSProperties = { fontSize: 12, color: 'var(--color-muted)', marginTop: 2 };

  return (
    <div style={container}>
      {days.map((d, idx) => {
        const key = iso(d);
        return (
          <button key={idx} style={dayStyle(d)} onClick={() => onSelectDate(d)}>
            <div style={{ fontWeight: 600 }}>{fmt(d)}</div>
            <div style={countStyle}>{counts[key] || 0} events</div>
          </button>
        );
      })}
    </div>
  );
}
