import type { SupabaseClient } from '@supabase/supabase-js'
import {
  queryOptions,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseQueryResult,
} from '@tanstack/react-query'

import { fetchInventoryTools, type InventoryTool } from '@/lib/inventory'
import { supabase } from '@/lib/supabase'

import { anonymousSessionOptions } from './use-anonymous-session'
import { userDataKey } from './use-user-data-overview'

/** Under the user-data key, so an import or a save refreshes it with the overview. */
export const inventoryToolsKey = [...userDataKey, 'tools'] as const

/** The user's tools with their latest results, read once the anonymous session exists. Disabled
 *  when Supabase is not configured. */
export function inventoryToolsOptions(queryClient: QueryClient, client: SupabaseClient | null) {
  return queryOptions({
    queryKey: inventoryToolsKey,
    queryFn: async (): Promise<InventoryTool[]> => {
      if (!client) throw new Error('Supabase is not configured.')
      await queryClient.query(anonymousSessionOptions(client))
      return fetchInventoryTools(client)
    },
    enabled: client !== null,
  })
}

/** The Inventory screen's tools. */
export function useInventoryTools(
  client: SupabaseClient | null = supabase,
): UseQueryResult<InventoryTool[]> {
  const queryClient = useQueryClient()
  return useQuery(inventoryToolsOptions(queryClient, client))
}
