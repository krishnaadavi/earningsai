export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';

export type WatchItem = { id: string; ticker: string };
export type WatchEvent = {
  id: string;
  ticker: string;
  company?: string | null;
  event_date: string; // ISO
  time_of_day?: string | null;
  status?: string | null;
};

export async function fetchWatchlist(): Promise<WatchItem[]> {
  try {
    const r = await fetch(`${API_BASE}/watchlist`);
    if (!r.ok) return [];
    const arr = await r.json();
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export async function fetchWatchlistEvents(startISO: string, endISO: string): Promise<WatchEvent[]> {
  try {
    const r = await fetch(`${API_BASE}/watchlist/events?start=${encodeURIComponent(startISO)}&end=${encodeURIComponent(endISO)}`);
    if (!r.ok) return [];
    const arr = await r.json();
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export async function addToWatchlist(ticker: string): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/watchlist/${encodeURIComponent(ticker)}`, { method: 'POST' });
    return r.ok;
  } catch {
    return false;
  }
}

export async function removeFromWatchlist(ticker: string): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/watchlist/${encodeURIComponent(ticker)}`, { method: 'DELETE' });
    return r.ok;
  } catch {
    return false;
  }
}
