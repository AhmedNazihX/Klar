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

import { anonymousSessionOptions } from './use-anonymous-session'

/** Every query on the user's own data sits under this key, so one invalidation re-reads them all
 *  after a write (an import, a saved run). */
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
      if (!client) throw new Error('Supabase is not configured.')
      await queryClient.query(anonymousSessionOptions(client))
      return fetchUserDataOverview(client)
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
