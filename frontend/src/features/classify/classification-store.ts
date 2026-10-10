import type { SupabaseClient } from '@supabase/supabase-js'
import { queryOptions, type QueryClient } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'
import { withAnonymousSession } from '@/hooks/use-anonymous-session'
import { fetchInventoryTool, type InventoryTool } from '@/lib/inventory'
import { logSkippedRead } from '@/lib/log'
import { fetchLatestRuns, type Answers, type ToolRun } from '@/lib/tool-runs'

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
  /** The run's number on its tool, as the database gave it; 1 when unknown (a run never saved,
   *  or one whose number couldn't be read back). */
  runNo?: number
  /** The run's row id in the user's data, when known, on a run an answer made: Undo answer
   *  deletes it by this id. */
  runId?: string
  /** The follow-up answers the run used (P5b), appended to `description` when it ran. */
  answers?: Answers
  /** The run before this one, when an answer made this one: what it changed, and what Undo
   *  answer restores (with whether it was saved). */
  previous?: PreviousRun
}

/** The run an answer replaced: Undo answer shows it again. It is never deleted from here (it has
 *  no `previous` to undo to), so its row id isn't kept. */
export type PreviousRun = Omit<ToolRun, 'id'> & {
  saveFailure?: ClassificationRun['saveFailure']
}

/** A run's number on its tool. */
export function runNumber(run: ClassificationRun): number {
  return run.runNo ?? 1
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

type FollowUp = Pick<ClassificationRun, 'runId' | 'answers' | 'previous'>

/** The answers the latest run used and the run before it, read only once a tool has a second
 *  run: a first run has neither. The run before counts only when an answer made the latest one
 *  (a run of an edited description starts afresh). A run read here that isn't the inventory's
 *  latest (written in between) is left out. A failed read leaves them out too: the result still
 *  shows, without what the last answer changed. */
async function followUpOf(client: SupabaseClient, tool: InventoryTool): Promise<FollowUp> {
  if (tool.runNo === null || tool.runNo < 2) return {}
  let runs: Awaited<ReturnType<typeof fetchLatestRuns>>
  try {
    runs = await fetchLatestRuns(client, tool.toolId)
  } catch (error) {
    logSkippedRead("Klar couldn't read the tool's last two runs.", error)
    return {}
  }
  const [latest, previous] = runs
  if (latest?.runNo !== tool.runNo || Object.keys(latest.answers).length === 0) return {}
  const before = previous && {
    runNo: previous.runNo,
    result: previous.result,
    answers: previous.answers,
  }
  return { runId: latest.id, answers: latest.answers, previous: before ?? undefined }
}

async function toToolResult(
  client: SupabaseClient,
  tool: InventoryTool | null,
): Promise<ToolResult> {
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
      runNo: tool.runNo ?? undefined,
      ...(await followUpOf(client, tool)),
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
      return toToolResult(sessionClient, await fetchInventoryTool(sessionClient, toolId))
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
