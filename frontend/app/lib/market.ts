export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';

export type Mover = {
  ticker: string;
  company?: string | null;
  price?: number | null;
  change?: number | null;
  change_percent?: number | null;
  direction?: 'up' | 'down' | 'flat' | null;
};

export async function fetchMarketMovers(limit = 20, tickers?: string[]): Promise<Mover[]> {
  try {
    const qs = new URLSearchParams();
    qs.set('limit', String(limit));
    if (tickers && tickers.length) qs.set('tickers', tickers.join(','));
    const r = await fetch(`${API_BASE}/market/movers?${qs.toString()}`);
    if (!r.ok) return [];
    const arr = await r.json();
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}
