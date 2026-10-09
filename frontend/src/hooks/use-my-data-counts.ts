import type { SupabaseClient } from '@supabase/supabase-js'
import { useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'

import { supabase } from '@/lib/supabase'
import { fetchMyDataCounts, type MyDataCounts } from '@/lib/user-data'

import { withAnonymousSession } from './use-anonymous-session'
import { userDataKey } from './use-user-data-overview'

export const myDataCountsKey = [...userDataKey, 'counts'] as const

/**
 * What Klar keeps for the user (my_data_counts), read once the anonymous session exists.
 * Disabled when Supabase is not configured.
 */
export function useMyDataCounts(
  client: SupabaseClient | null = supabase,
): UseQueryResult<MyDataCounts> {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: myDataCountsKey,
    queryFn: async () => fetchMyDataCounts(await withAnonymousSession(queryClient, client)),
    enabled: client !== null,
  })
}
