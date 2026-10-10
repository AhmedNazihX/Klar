import type { SupabaseClient } from '@supabase/supabase-js'
import { z } from 'zod'

import type { ClassificationResult } from '@/api'

import { hasAssessedClass } from './risk-class'
import { parseStoredResult } from './stored-result'

// One tool's runs in Supabase (story P5b): the follow-up loop adds a run with the answers it used
// (P19's `inputs`), reads the latest two back to show what the last answer changed, and undoes
// an answer by deleting the latest run, by its row id: the database reuses a deleted run's number,
// so a stale tab deleting by number could take a newer run. Owner-only RLS applies to every call
// (P3); the database numbers each run (run_no) and stamps its times, whatever the browser sends.

/** The answers a run used, by follow-up question id; appended to the description (decision 019). */
export type Answers = Readonly<Record<string, string>>

/** A stored run's row id and its number on the tool. */
export type RunRef = { id: string; runNo: number }

/** One stored run of a tool. */
export type ToolRun = RunRef & {
  result: ClassificationResult
  answers: Answers
}

const RUN_COLUMNS = 'id, run_no, result, inputs'

/** A row's inputs as P19 stores them; null on rows written before P19. Untrusted: the browser
 *  wrote it, so a malformed one is read as no answers. */
const InputsSchema = z.object({
  description: z.string(),
  answers: z.record(z.string(), z.string()).optional(),
})

const RunRefSchema = z.object({ id: z.uuid(), run_no: z.number().int().positive() })

const RunRowSchema = RunRefSchema.extend({ result: z.unknown(), inputs: z.unknown() })

function toRun(row: z.infer<typeof RunRowSchema>): ToolRun | null {
  const result = parseStoredResult(row.result)
  if (!result || !hasAssessedClass(result)) return null
  const inputs = InputsSchema.safeParse(row.inputs)
  const answers = inputs.success ? (inputs.data.answers ?? {}) : {}
  return { id: row.id, runNo: row.run_no, result, answers }
}

/** The tool's latest two runs, newest first; a run Klar can't read comes back as null. */
export async function fetchLatestRuns(
  client: SupabaseClient,
  toolId: string,
): Promise<[ToolRun | null, ToolRun | null]> {
  const runs = await client
    .from('classifications')
    .select(RUN_COLUMNS)
    .eq('system_id', toolId)
    .order('run_no', { ascending: false })
    .limit(2)
  if (runs.error) throw runs.error
  const [latest, previous] = z.array(RunRowSchema).parse(runs.data).map(toRun)
  return [latest ?? null, previous ?? null]
}

export type FollowUpRun = {
  toolId: string
  /** The description as the user wrote it; the answers are stored beside it, not in it. */
  description: string
  answers: Answers
  result: ClassificationResult
}

/** The tool's latest run's number, or null while it has none: a run just saved through
 *  save_classified_tool, which returns only the tool's id. */
export async function fetchLatestRunNo(
  client: SupabaseClient,
  toolId: string,
): Promise<number | null> {
  const runs = await client
    .from('classifications')
    .select('run_no')
    .eq('system_id', toolId)
    .order('run_no', { ascending: false })
    .limit(1)
  if (runs.error) throw runs.error
  const [latest] = z.array(RunRefSchema.pick({ run_no: true })).parse(runs.data)
  return latest?.run_no ?? null
}

/** Adds a re-run with its answers as the tool's next run, and resolves with its id and number.
 *  The tool keeps its name and description: only the answers changed. */
export async function addFollowUpRun(client: SupabaseClient, run: FollowUpRun): Promise<RunRef> {
  const added = await client
    .from('classifications')
    .insert({
      system_id: run.toolId,
      risk_class: run.result.risk_class,
      status: run.result.status,
      law_version: run.result.law_version,
      result: run.result,
      inputs: { description: run.description, answers: run.answers },
    })
    .select('id, run_no')
    .single()
  if (added.error) throw added.error
  const ref = RunRefSchema.parse(added.data)
  return { id: ref.id, runNo: ref.run_no }
}

/** Deletes the run with row id `runId` (Undo answer: the run before it is the latest again), and
 *  resolves with whether it was there to delete: false when another tab or device deleted it
 *  first, so the tool's runs changed elsewhere. */
export async function deleteRun(client: SupabaseClient, runId: string): Promise<boolean> {
  const deleted = await client.from('classifications').delete().eq('id', runId).select('id')
  if (deleted.error) throw deleted.error
  return z.array(z.object({ id: z.uuid() })).parse(deleted.data).length > 0
}
