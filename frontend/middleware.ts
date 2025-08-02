// middleware.ts
// Next.js middleware for Supabase Auth with optimized JWT verification
// Uses asymmetric keys for local JWT verification when possible
// RELEVANT FILES: lib/supabase/server.ts, lib/supabase/client.ts, lib/supabase/jwt-verify.ts

import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'
import { isTokenExpired, getClaims } from '@/lib/supabase/jwt-verify'

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => {
            request.cookies.set(name, value)
            response.cookies.set(name, value, options)
          })
        },
      },
    }
  )

  // Try to get session from cookies for optimized verification
  const accessToken = request.cookies.get('sb-access-token')?.value
  let isAuthenticated = false
  let needsRefresh = false

  if (accessToken) {
    try {
      // First try local JWT verification for performance
      const claims = getClaims(accessToken)
      isAuthenticated = claims !== null && !isTokenExpired(accessToken)
      
      // If token is close to expiring, mark for refresh
      if (claims?.exp) {
        const expiresIn = claims.exp * 1000 - Date.now()
        needsRefresh = expiresIn < 300000 // Refresh if less than 5 minutes
      }
    } catch {
      // If local verification fails, fall back to server verification
      isAuthenticated = false
    }
  }

  // If local verification failed or token needs refresh, use Supabase client
  if (!isAuthenticated || needsRefresh) {
    const { data: { user } } = await supabase.auth.getUser()
    isAuthenticated = !!user
  }

  // Protected routes
  if (request.nextUrl.pathname.startsWith('/dashboard')) {
    if (!isAuthenticated) {
      // Redirect to login if not authenticated
      const loginUrl = new URL('/login', request.url)
      loginUrl.searchParams.set('redirect', request.nextUrl.pathname)
      return NextResponse.redirect(loginUrl)
    }
  }

  // Auth routes (login, register) - redirect to dashboard if already logged in
  if (['/login', '/register'].includes(request.nextUrl.pathname)) {
    if (isAuthenticated) {
      return NextResponse.redirect(new URL('/dashboard', request.url))
    }
  }

  return response
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}