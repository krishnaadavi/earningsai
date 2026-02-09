import type { NextRequest } from 'next/server';
import { NextResponse } from 'next/server';

export function middleware(_: NextRequest) {
  // No-op: rely on app/page.tsx to redirect to /dashboard
  return NextResponse.next();
}

export const config = {
  matcher: [],
};
