import type { SupabaseClient } from '@supabase/supabase-js'
import {
  queryOptions,
  useQuery,
  type QueryClient,
  type UseQueryResult,
} from '@tanstack/react-query'

import { ensureAnonymousSession } from '@/lib/auth'
import { supabase } from '@/lib/supabase'

const anonymousSessionKey = ['auth', 'anonymous-session'] as const

/**
 * The anonymous session as a query. Everything that needs the session goes through this one key,
 * so two screens starting at once never sign in twice (which would make two anonymous users).
 */
export function anonymousSessionOptions(client: SupabaseClient | null) {
  return queryOptions({
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

/** Whether this tab has started its anonymous session: the session's query holds a user id. */
export function hasAnonymousSession(queryClient: QueryClient): boolean {
  return queryClient.getQueryData(anonymousSessionKey) !== undefined
}

/**
 * Marks this tab's session as ended without starting a new one. Nothing signs in until a read or
 * write needs the session again (withAnonymousSession, or a screen mounting
 * useAnonymousSession); that one fetch reuses a session another tab has stored since, and signs
 * in only when there is none.
 */
export function endAnonymousSession(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: anonymousSessionKey, refetchType: 'none' })
}

/**
 * Waits for the anonymous session (through its one query) before a read or write of the user's
 * own data, and returns the client to run it on. Throws when Supabase is not configured. After
 * endAnonymousSession, this is what starts the next session.
 */
export async function withAnonymousSession(
  queryClient: QueryClient,
  client: SupabaseClient | null,
): Promise<SupabaseClient> {
  if (!client) throw new Error('Supabase is not configured.')
  await queryClient.query(anonymousSessionOptions(client))
  return client
}

/**
 * The visitor's user id, signing in anonymously on first use. Disabled (no data) when Supabase is
 * not configured. supabase-js refreshes the tokens itself, so the id never goes stale.
 */
export function useAnonymousSession(
  client: SupabaseClient | null = supabase,
): UseQueryResult<string> {
  return useQuery(anonymousSessionOptions(client))
}
