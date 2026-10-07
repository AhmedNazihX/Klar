import type { SupabaseClient } from '@supabase/supabase-js'
import {
  queryOptions,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseQueryResult,
} from '@tanstack/react-query'

import { fetchUserDataOverview, type UserDataOverview } from '@/lib/company-profile'
import { supabase } from '@/lib/supabase'

import { withAnonymousSession } from './use-anonymous-session'

/** Every query over the user's saved data starts with this key, so a write (an import, a saved
 *  run) can refresh them all, and a sign-out forget them. */
export const userDataKey = ['user-data'] as const
export const userDataOverviewKey = [...userDataKey, 'overview'] as const

/**
 * The user's company profile and tool count, read once the anonymous session exists (through the
 * session's own query, so it never signs in twice). Disabled when Supabase is not configured.
 */
export function userDataOverviewOptions(queryClient: QueryClient, client: SupabaseClient | null) {
  return queryOptions({
    queryKey: userDataOverviewKey,
    queryFn: async (): Promise<UserDataOverview> => {
      return fetchUserDataOverview(await withAnonymousSession(queryClient, client))
    },
    enabled: client !== null,
  })
}

/** The company profile (for the Welcome screen and the sidebar) and how many tools exist. */
export function useUserDataOverview(
  client: SupabaseClient | null = supabase,
): UseQueryResult<UserDataOverview> {
  const queryClient = useQueryClient()
  return useQuery(userDataOverviewOptions(queryClient, client))
}
