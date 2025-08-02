// lib/supabase/client.ts
// Browser-side Supabase client
// Used for client components and browser-based auth operations
// RELEVANT FILES: server.ts, middleware.ts

import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY!
  )
}