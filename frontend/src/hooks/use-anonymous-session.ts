import type { SupabaseClient } from '@supabase/supabase-js'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { ensureAnonymousSession } from '@/lib/auth'
import { supabase } from '@/lib/supabase'

export const anonymousSessionKey = ['auth', 'anonymous-session'] as const

/**
 * The visitor's user id, signing in anonymously on first use. Disabled (no data) when Supabase is
 * not configured. supabase-js refreshes the tokens itself, so the id never goes stale.
 */
export function useAnonymousSession(
  client: SupabaseClient | null = supabase,
): UseQueryResult<string> {
  return useQuery({
    queryKey: anonymousSessionKey,
    queryFn: () => {
      if (!client) throw new Error('Supabase is not configured.')
      return ensureAnonymousSession(client)
    },
    enabled: client !== null,
    staleTime: Infinity,
    gcTime: Infinity,
  })
}
