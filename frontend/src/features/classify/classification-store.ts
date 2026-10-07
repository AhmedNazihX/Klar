import type { SupabaseClient } from '@supabase/supabase-js'
import { queryOptions, type QueryClient } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'
import { withAnonymousSession } from '@/hooks/use-anonymous-session'
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

/** What a tool's result page shows: its latest run, the tool without a result (never checked,
 *  or a saved result Klar can't read), or nothing (no such tool). */
export type ToolResult =
  | { kind: 'run'; run: ClassificationRun }
  | { kind: 'no-result' | 'unreadable'; tool: InventoryTool }
  | { kind: 'missing' }

/** Every run's query starts with this key, so a sign-out can forget them all. */
export const classificationRunKey = ['classification-run'] as const

/** A tool's result page, under the runs' key (a sign-out forgets it with them). */
export function toolResultKey(toolId: string) {
  return [...classificationRunKey, toolId] as const
}

function toToolResult(tool: InventoryTool | null): ToolResult {
  if (!tool) return { kind: 'missing' }
  if (tool.hasUnreadableResult) return { kind: 'unreadable', tool }
  if (!tool.result) return { kind: 'no-result', tool }
  return {
    kind: 'run',
    run: {
      toolId: tool.toolId,
      name: tool.name,
      description: tool.description,
      result: tool.result,
      isStored: true,
    },
  }
}

/**
 * A tool's result page, in one read. The Classify screen puts a fresh run in the cache under its
 * tool id when the stream ends (putRun); any other tool loads from the user's inventory. Without
 * Supabase there is nothing to load: a tool that isn't in the cache is missing.
 */
export function toolResultOptions(
  queryClient: QueryClient,
  client: SupabaseClient | null,
  toolId: string,
) {
  return queryOptions({
    queryKey: toolResultKey(toolId),
    queryFn: async (): Promise<ToolResult> => {
      if (!client) return { kind: 'missing' }
      const sessionClient = await withAnonymousSession(queryClient, client)
      return toToolResult(await fetchInventoryTool(sessionClient, toolId))
    },
    // A run stays as it was read or made (a fresh one keeps saying whether it was saved). A tool
    // without one is read again on each visit, so an import or a run since then shows.
    staleTime: (query) => (query.state.data?.kind === 'run' ? Infinity : 0),
    gcTime: Infinity,
  })
}

/** Shows `run` on its tool's result page, without reading it back. */
export function putRun(queryClient: QueryClient, run: ClassificationRun): void {
  queryClient.setQueryData(toolResultKey(run.toolId), { kind: 'run', run })
}

/** The tool a draft's run is saved on, with the name it had when "Classify this tool" was used. */
export type DraftTool = { toolId: string; name: string | null }

/** The description being worked on, and the tool it is for: null for a new tool; the tool after
 *  "Classify this tool", so the run is saved on that tool. */
export type ClassifyDraft = { values: DescriptionFormValues; tool: DraftTool | null }

const EMPTY_DRAFT: ClassifyDraft = { values: { name: '', description: '' }, tool: null }
let savedDraft: ClassifyDraft = EMPTY_DRAFT

/** The draft kept for this session: "Save for later", "Edit description" and "Classify this
 *  tool" bring it back to the form. Never sent anywhere until the user runs the checks. */
export function readDraft(): ClassifyDraft {
  return savedDraft
}

export function saveDraft(values: DescriptionFormValues, tool: DraftTool | null = null): void {
  savedDraft = { values: { ...values }, tool }
}

export function clearDraft(): void {
  savedDraft = EMPTY_DRAFT
}
