import type { SupabaseClient } from '@supabase/supabase-js'
import { queryOptions, type QueryClient } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'
import { anonymousSessionOptions } from '@/hooks/use-anonymous-session'
import { userDataKey } from '@/hooks/use-user-data-overview'
import { fetchInventoryTool, type InventoryTool } from '@/lib/inventory'

import type { DescriptionFormValues } from './description-form'

/** One finished run: what was asked, and the engine's result. `name` is null when the user gave
 *  none: screens then show "Your tool" in the reader's language. */
export type ClassificationRun = {
  toolId: string
  name: string | null
  description: string
  result: ClassificationResult
  /** Set on a fresh run that couldn't be saved to the inventory: it lives only in this tab. */
  saveFailure?: 'storage-full' | 'failed'
  /** Read back from the user's data rather than just run: the browser wrote it (P3), so the
   *  screens say Klar doesn't re-check it and show the app's own notice, not the stored one. */
  isStored?: boolean
}

export function classificationRunKey(toolId: string) {
  return ['classification-run', toolId] as const
}

/**
 * A tool's latest run. The Classify screen puts a fresh run in the cache under its tool id when
 * the stream ends; any other tool loads from the user's inventory. Null when the user has no such
 * tool, it has no readable result, or Supabase is not configured (inventoryToolOptions tells
 * those apart).
 */
export function classificationRunOptions(
  queryClient: QueryClient,
  client: SupabaseClient | null,
  toolId: string,
) {
  return queryOptions({
    queryKey: classificationRunKey(toolId),
    queryFn: async (): Promise<ClassificationRun | null> => {
      if (!client) return null
      await queryClient.query(anonymousSessionOptions(client))
      const tool = await fetchInventoryTool(client, toolId)
      if (!tool?.result) return null
      return {
        toolId: tool.toolId,
        name: tool.name,
        description: tool.description,
        result: tool.result,
        isStored: true,
      }
    },
    staleTime: Infinity,
    gcTime: Infinity,
  })
}

/**
 * The tool itself, for a result page with no run to show: whether the tool exists without a
 * saved result, with one that can't be read, or not at all (null). Null too without Supabase.
 */
export function inventoryToolOptions(
  queryClient: QueryClient,
  client: SupabaseClient | null,
  toolId: string,
) {
  return queryOptions({
    // Under the user-data key, so an import or a save reads it again.
    queryKey: [...userDataKey, 'tool', toolId] as const,
    queryFn: async (): Promise<InventoryTool | null> => {
      if (!client) return null
      await queryClient.query(anonymousSessionOptions(client))
      return fetchInventoryTool(client, toolId)
    },
  })
}

const EMPTY_DRAFT: DescriptionFormValues = { name: '', description: '' }
let savedDraft: DescriptionFormValues = EMPTY_DRAFT

/** The description being worked on, kept for this session: "Save for later" and "Edit
 *  description" bring it back to the form. Never sent anywhere until the user runs the checks. */
export function readDraft(): DescriptionFormValues {
  return savedDraft
}

export function saveDraft(draft: DescriptionFormValues): void {
  savedDraft = { ...draft }
}

export function clearDraft(): void {
  savedDraft = EMPTY_DRAFT
}
