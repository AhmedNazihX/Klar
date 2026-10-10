import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'
import { saveClassifiedTool } from '@/lib/inventory'
import { logSkippedRead } from '@/lib/log'
import { supabase } from '@/lib/supabase'
import { fetchLatestRunNo } from '@/lib/tool-runs'

import { withAnonymousSession } from './use-anonymous-session'
import { userDataKey, userDataOverviewOptions } from './use-user-data-overview'

export type SaveClassifiedToolVariables = {
  /** The tool the run is saved on, as its next run; null to save it as a new tool. */
  toolId: string | null
  /** Null when the user gave none: the name is never filled in with a placeholder. */
  name: string | null
  description: string
  result: ClassificationResult
  /** The name a new inventory gets when the user has none yet. */
  inventoryName: string
}

/** A saved run: its tool, and the run's number when it could be read back. */
export type SavedRun = { toolId: string; runNo: number | null }

/** The saved run's number (on a tool that had runs, it isn't run 1). The run is saved whatever
 *  this read says: a failed read only leaves it unknown. */
async function readBack(client: SupabaseClient, toolId: string): Promise<number | null> {
  try {
    return await fetchLatestRunNo(client, toolId)
  } catch (error) {
    logSkippedRead("Klar couldn't read back the number of the run it saved.", error)
    return null
  }
}

/**
 * Saves a finished run in the user's inventory, on the given tool or as a new one, and resolves
 * with the tool's id and the run's number (save_classified_tool returns only the tool's, so the
 * number is read back); with Supabase not configured, nothing is saved and it resolves with null.
 * Re-reads the user's data afterwards (the inventory and the overview's tool count).
 */
export function useSaveClassifiedTool(
  client: SupabaseClient | null = supabase,
): UseMutationResult<SavedRun | null, unknown, SaveClassifiedToolVariables> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ toolId, name, description, result, inventoryName }) => {
      if (!client) return null
      const sessionClient = await withAnonymousSession(queryClient, client)
      // The inventory the profile lives on (the overview's), so tools and profile stay together.
      const overview = await queryClient.query(userDataOverviewOptions(queryClient, client))
      const savedId = await saveClassifiedTool(sessionClient, {
        toolId,
        inventoryId: overview.inventoryId,
        inventoryName,
        name,
        description,
        result,
      })
      return { toolId: savedId, runNo: await readBack(sessionClient, savedId) }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: userDataKey }),
  })
}
