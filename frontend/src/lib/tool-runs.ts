import type { SupabaseClient } from '@supabase/supabase-js'
import { z } from 'zod'

import type { ClassificationResult } from '@/api'

import { hasAssessedClass } from './risk-class'
import { parseStoredResult } from './stored-result'

// One tool's runs in Supabase (story P5b): the follow-up loop adds a run with the answers it used
// (P19's `inputs`), reads the latest two back to show what the last answer changed, and undoes
// an answer by deleting the latest run. Owner-only RLS applies to every call (P3); the database
// numbers each run (run_no) and stamps its times, whatever the browser sends.

/** The answers a run used, by follow-up question id; appended to the description (decision 019). */
export type Answers = Readonly<Record<string, string>>

/** One stored run of a tool. */
export type ToolRun = {
  runNo: number
  result: ClassificationResult
  answers: Answers
}

const RUN_COLUMNS = 'run_no, result, inputs'

/** A row's inputs as P19 stores them; null on rows written before P19. Untrusted: the browser
 *  wrote it, so a malformed one is read as no answers. */
const InputsSchema = z.object({
  description: z.string(),
  answers: z.record(z.string(), z.string()).optional(),
})

const RunRowSchema = z.object({
  run_no: z.number().int().positive(),
  result: z.unknown(),
  inputs: z.unknown(),
})

function toRun(row: z.infer<typeof RunRowSchema>): ToolRun | null {
  const result = parseStoredResult(row.result)
  if (!result || !hasAssessedClass(result)) return null
  const inputs = InputsSchema.safeParse(row.inputs)
  return { runNo: row.run_no, result, answers: inputs.success ? (inputs.data.answers ?? {}) : {} }
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

/** Adds a re-run with its answers as the tool's next run, and resolves with its number. The tool
 *  keeps its name and description: only the answers changed. */
export async function addFollowUpRun(client: SupabaseClient, run: FollowUpRun): Promise<number> {
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
    .select('run_no')
    .single()
  if (added.error) throw added.error
  return z.object({ run_no: z.number().int().positive() }).parse(added.data).run_no
}

/** Deletes the tool's run `runNo` (Undo answer: the run before it is the latest again). */
export async function deleteRun(
  client: SupabaseClient,
  toolId: string,
  runNo: number,
): Promise<void> {
  const deleted = await client
    .from('classifications')
    .delete()
    .eq('system_id', toolId)
    .eq('run_no', runNo)
  if (deleted.error) throw deleted.error
}
