import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'
import { saveClassifiedTool } from '@/lib/inventory'
import { supabase } from '@/lib/supabase'

import { anonymousSessionOptions } from './use-anonymous-session'
import { userDataKey, userDataOverviewOptions } from './use-user-data-overview'

export type SaveClassifiedToolVariables = {
  name: string
  description: string
  result: ClassificationResult
  /** The name a new inventory gets when the user has none yet. */
  inventoryName: string
}

/**
 * Saves a finished run as a new tool in the user's inventory and resolves with its id; with
 * Supabase not configured, nothing is saved and it resolves with null. Re-reads the user's data
 * afterwards (the inventory and the overview's tool count).
 */
export function useSaveClassifiedTool(
  client: SupabaseClient | null = supabase,
): UseMutationResult<string | null, unknown, SaveClassifiedToolVariables> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ name, description, result, inventoryName }) => {
      if (!client) return null
      await queryClient.query(anonymousSessionOptions(client))
      // The inventory the profile lives on (the overview's), so tools and profile stay together.
      const overview = await queryClient.query(userDataOverviewOptions(queryClient, client))
      return saveClassifiedTool(client, {
        inventoryId: overview.inventoryId,
        inventoryName,
        name,
        description,
        result,
      })
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: userDataKey }),
  })
}
