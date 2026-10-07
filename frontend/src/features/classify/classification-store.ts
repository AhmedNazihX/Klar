import type { SupabaseClient } from '@supabase/supabase-js'
import { queryOptions, type QueryClient } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'
import { anonymousSessionOptions } from '@/hooks/use-anonymous-session'
import { fetchInventoryTool } from '@/lib/inventory'

import type { DescriptionFormValues } from './description-form'

/** One finished run: what was asked, and the engine's result. `name` is as the user typed it,
 *  possibly empty: screens then show "Your tool" in the reader's language. */
export type ClassificationRun = {
  toolId: string
  name: string
  description: string
  result: ClassificationResult
  /** Set on a fresh run that couldn't be saved to the inventory: it lives only in this tab. */
  saveFailure?: 'storage-full' | 'failed'
}

export function classificationRunKey(toolId: string) {
  return ['classification-run', toolId] as const
}

/**
 * A tool's latest run. The Classify screen puts a fresh run in the cache under its tool id when
 * the stream ends; any other tool loads from the user's inventory. Null when the user has no such
 * tool, it has no readable result, or Supabase is not configured.
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
      }
    },
    staleTime: Infinity,
    gcTime: Infinity,
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
