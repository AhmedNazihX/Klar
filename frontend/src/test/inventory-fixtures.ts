// Inventory fixtures (P6): inventory_tools rows as PostgREST returns them, and the two result
// layouts classify-fixtures.ts has no variant for (prohibited, legally ambiguous). Like the
// variants there, they are hand-made from the recorded worked example, changing only the fields
// the inventory reads; they are fixtures, not engine output.
import { http, HttpResponse, type HttpHandler } from 'msw'

import type { Citation, ClassificationResult } from '@/api'

import { decidedHighRisk } from './classify-fixtures'
import { SUPABASE_URL } from './supabase-fixtures'

export const INVENTORY_TOOLS_URL = `${SUPABASE_URL}/rest/v1/inventory_tools`
/** save_classified_tool: a classified tool, its inventory if needed and its first run, at once;
 *  or the next run on a tool the user has. */
export const SAVE_TOOL_URL = `${SUPABASE_URL}/rest/v1/rpc/save_classified_tool`
/** A tool's runs (P5b reads a saved run's id and number back from here). */
export const CLASSIFICATIONS_URL = `${SUPABASE_URL}/rest/v1/classifications`

/** A saved run's row id. */
export const SAVED_RUN_ID = '7f3e9a10-2b4c-4d5e-8f60-718293a4b5c6'

/** GET classifications answers with the saved run's id and number (`runNo`), the read-back after
 *  save_classified_tool. */
export function savedRunHandler(runNo = 1): HttpHandler {
  return http.get(CLASSIFICATIONS_URL, () =>
    HttpResponse.json([{ id: SAVED_RUN_ID, run_no: runNo }]),
  )
}

const ART_5_1_F: Citation = {
  provision_id: 'art:5:1:f',
  document_id: 'ai-act-consolidated',
  language: 'en',
  quote:
    'the placing on the market, the putting into service for this specific purpose, or the use of AI systems to infer emotions of a natural person in the areas of workplace and education institutions',
}

/** A deployer's tool that reads staff emotions at work: prohibited by Art. 5(1)(f). */
export function prohibitedResult(): ClassificationResult {
  const base = decidedHighRisk()
  return {
    ...base,
    risk_class: 'prohibited',
    annex_point: null,
    obligations: [],
    steps: base.steps.map((step) =>
      step.step === 'prohibited'
        ? { ...step, decision: 'Banned: it infers emotions at work.', citations: [ART_5_1_F] }
        : step,
    ),
  }
}

const ART_6_3: Citation = {
  provision_id: 'art:6:3',
  document_id: 'ai-act-consolidated',
  language: 'en',
  quote:
    'an AI system referred to in Annex III shall not be considered to be high-risk where it does not pose a significant risk of harm',
}

/** The high-risk check left open between two readings of Art. 6(3); the stricter one applies. */
export function ambiguousResult(): ClassificationResult {
  const base = decidedHighRisk()
  return {
    ...base,
    status: 'legally_ambiguous',
    steps: base.steps.map((step) =>
      step.step === 'high_risk'
        ? {
            ...step,
            status: 'legally_ambiguous',
            open_question: {
              question: 'Is copying CV details a narrow procedural task?',
              readings: [
                {
                  title: 'High-risk',
                  risk_class: 'high_risk',
                  explanation: 'It feeds the recruitment decision.',
                  citation: ART_6_3,
                  is_applied: true,
                },
                {
                  title: 'Not high-risk',
                  risk_class: 'minimal_risk',
                  explanation: 'It only copies data.',
                  citation: ART_6_3,
                },
              ],
            },
          }
        : step,
    ),
  }
}

let nextId = 0

/** A uuid for a fixture tool, distinct within a test run. */
export function toolId(): string {
  nextId += 1
  return `00000000-0000-4000-8000-${String(nextId).padStart(12, '0')}`
}

/** An inventory_tools row: a tool with its latest result, or with none (`result` null). */
export function toolRow(
  name: string,
  result: unknown,
  fields: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id: toolId(),
    name,
    description: `${name}: what it does.\nMore detail on a second line.`,
    created_at: '2026-10-01T09:00:00+00:00',
    run_no: result === null ? null : 1,
    result,
    ...fields,
  }
}

/** GET inventory_tools answers with these rows (a single tool's read filters them by id). */
export function inventoryToolsHandler(rows: () => Record<string, unknown>[]): HttpHandler {
  return http.get(INVENTORY_TOOLS_URL, ({ request }) => {
    const filter = new URL(request.url).searchParams.get('id')
    const all = rows()
    return HttpResponse.json(
      filter ? all.filter((row) => `eq.${String(row['id'])}` === filter) : all,
    )
  })
}
