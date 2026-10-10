// The follow-up loop with Supabase configured (P5b, P19): a re-run is saved as the tool's next
// run with the answers it used, a stored tool shows what its last answer changed, Undo answer
// deletes the latest run, and the company profile pre-selects the EU answer (decision 026 item 2).
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ClassificationResult, ClassifyRequest, FollowUpQuestion } from '@/api'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import {
  ANNEX_III_QUESTION,
  annexIIINeedsInfo,
  classifyHandler,
  decidedHighRisk,
  minimalRisk,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { toolRow } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { SUPABASE_URL } from '@/test/supabase-fixtures'
import { renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS, inventoryRow, userDataHandlers } from '@/test/user-data-handlers'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

const CLASSIFICATIONS_URL = `${SUPABASE_URL}/rest/v1/classifications`
const ANSWER = `${ANNEX_III_QUESTION} No.`

type Row = Record<string, unknown>

let inventories: Row[] = []
let tools: Row[] = []
/** The tool's classifications rows, as the table holds them. */
let runs: Row[] = []
let inserts: Row[] = []
let deletes: string[] = []
let classifyBodies: ClassifyRequest[] = []

/** PostgREST for classifications: reads newest first, inserts numbered by the "database", and
 *  deletes by system and run number. */
function classificationsHandlers(insertError: { status: number; code: string } | null = null) {
  return [
    http.get(CLASSIFICATIONS_URL, () =>
      HttpResponse.json(
        [...runs].sort((a, b) => Number(b['run_no']) - Number(a['run_no'])).slice(0, 2),
      ),
    ),
    http.post(CLASSIFICATIONS_URL, async ({ request }) => {
      const row = (await request.json()) as Row
      inserts.push(row)
      if (insertError) {
        return HttpResponse.json(
          { code: insertError.code, message: 'refused' },
          { status: insertError.status },
        )
      }
      const runNo = runs.length + 1
      runs.push({ ...row, run_no: runNo })
      return HttpResponse.json({ run_no: runNo }, { status: 201 })
    }),
    http.delete(CLASSIFICATIONS_URL, ({ request }) => {
      deletes.push(new URL(request.url).search)
      return new HttpResponse(null, { status: 204 })
    }),
  ]
}

beforeEach(() => {
  inventories = [inventoryRow()]
  tools = []
  runs = []
  inserts = []
  deletes = []
  classifyBodies = []
  server.use(
    ...userDataHandlers(
      () => inventories,
      () => tools.length,
      () => tools,
    ),
    ...classificationsHandlers(),
    classifyHandler(
      [...WORKED_EXAMPLE_EVENTS.slice(0, -1), { event: 'result', result: minimalRisk() }],
      (body) => {
        classifyBodies.push(body as ClassifyRequest)
      },
    ),
  )
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

/** One stored tool whose latest run is `result` (run `runNo`). */
function storeTool(result: ClassificationResult, runNo = 1): string {
  const row = toolRow('Shift planner', result, { run_no: runNo })
  tools = [row]
  return String(row['id'])
}

async function openTool(toolId: string, language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  renderRoute(`/app/inventory/${toolId}`)
  await screen.findByRole(
    'heading',
    { level: 1, name: 'Shift planner' },
    { timeout: FIRST_RENDER_MS },
  )
  return user
}

async function answerNo(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
  await user.click(within(question).getByRole('button', { name: 'No' }))
  await user.click(within(question).getByRole('button', { name: 'Add answer and run again' }))
}

describe('Saving a follow-up run', () => {
  it("adds the re-run as the tool's next run, with the answers beside the description", async () => {
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [{ run_no: 1, result: annexIIINeedsInfo(), inputs: null }]
    const user = await openTool(toolId)
    await answerNo(user)

    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    expect(banner).toHaveTextContent('Run 2 of 2')
    const description = String(tools[0]?.['description'])
    expect(classifyBodies).toEqual([
      { description, language: 'en', answers: { used_for_recruitment: ANSWER } },
    ])
    expect(inserts).toEqual([
      {
        system_id: toolId,
        risk_class: 'minimal_risk',
        status: 'decided',
        law_version: 'amended',
        result: minimalRisk(),
        inputs: { description, answers: { used_for_recruitment: ANSWER } },
      },
    ])
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('Undo answer deletes the latest run and shows the run before', async () => {
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [{ run_no: 1, result: annexIIINeedsInfo(), inputs: null }]
    const user = await openTool(toolId)
    await answerNo(user)
    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })

    await user.click(within(banner).getByRole('button', { name: 'Undo answer' }))
    expect(await screen.findByRole('region', { name: ANNEX_III_QUESTION })).toBeVisible()
    expect(deletes).toEqual([`?system_id=eq.${toolId}&run_no=eq.2`])
  })

  it.each([
    [
      'en',
      'No',
      'Add answer and run again',
      'Undo answer',
      "Klar couldn't undo your answer. Please try again.",
    ],
    [
      'de',
      'Nein',
      'Antwort hinzufügen und erneut prüfen',
      'Antwort rückgängig machen',
      'Klar konnte Ihre Antwort nicht rückgängig machen. Bitte versuchen Sie es erneut.',
    ],
  ] as const)(
    'an undo the database refuses keeps the re-run and says so (%s)',
    async (language, no, runAgain, undo, failed) => {
      server.use(
        http.delete(CLASSIFICATIONS_URL, () =>
          HttpResponse.json({ code: '42501', message: 'refused' }, { status: 403 }),
        ),
      )
      const toolId = storeTool(annexIIINeedsInfo())
      const user = await openTool(toolId, language)
      const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
      await user.click(within(question).getByRole('button', { name: no }))
      await user.click(within(question).getByRole('button', { name: runAgain }))
      const undoButton = await screen.findByRole('button', { name: undo })

      await user.click(undoButton)
      expect(await screen.findByRole('alert')).toHaveTextContent(failed)
      // The re-run stays the result shown, as it stays the tool's latest run.
      expect(screen.queryByRole('region', { name: ANNEX_III_QUESTION })).toBeNull()
    },
  )

  it('a re-run the inventory refuses still shows, with a note that it was not saved', async () => {
    server.use(...classificationsHandlers({ status: 400, code: 'PT507' }))
    const toolId = storeTool(annexIIINeedsInfo())
    const user = await openTool(toolId)
    await answerNo(user)

    expect(await screen.findByRole('alert')).toHaveAttribute('data-failure', 'storage-full')
    expect(
      screen.getByRole('region', { name: 'Your answer changed the result.' }),
    ).toHaveTextContent('Run 2 of 2')
    // Undo then deletes nothing: the run was never saved.
    await user.click(screen.getByRole('button', { name: 'Undo answer' }))
    expect(await screen.findByRole('region', { name: ANNEX_III_QUESTION })).toBeVisible()
    expect(deletes).toEqual([])
  })
})

describe('A stored tool after an answer', () => {
  it('shows what its last answer changed, read from its last two runs', async () => {
    const toolId = storeTool(minimalRisk(), 2)
    runs = [
      { run_no: 1, result: annexIIINeedsInfo(), inputs: { description: 'd', answers: {} } },
      {
        run_no: 2,
        result: minimalRisk(),
        inputs: { description: 'd', answers: { used_for_recruitment: ANSWER } },
      },
    ]
    await openTool(toolId, 'de')
    const banner = await screen.findByRole('region', {
      name: 'Ihre Antwort hat das Ergebnis geändert.',
    })
    expect(banner).toHaveTextContent('Durchlauf 2 von 2')
    expect(banner).toHaveTextContent(`Sie haben angegeben: „${ANSWER}“`)
  })

  it.each([
    ['an edited description', { description: 'edited', answers: {} }],
    ['a run stored before P19 (no inputs)', null],
    ['inputs Klar cannot read', { answers: 'not a map' }],
  ])('shows no change for a second run from %s', async (_, inputs) => {
    const toolId = storeTool(minimalRisk(), 2)
    runs = [
      { run_no: 1, result: annexIIINeedsInfo(), inputs: null },
      { run_no: 2, result: minimalRisk(), inputs },
    ]
    await openTool(toolId)
    // The stored result still shows; only the banner of an answer's re-run is left out.
    expect(
      within(screen.getByRole('region', { name: 'Result' })).getByText('Minimal risk'),
    ).toBeVisible()
    expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
  })
})

describe('The company profile pre-selects the EU answer (decision 026 item 2)', () => {
  const EU_LINK: FollowUpQuestion = {
    id: 'eu_link',
    text: 'Is the system placed on the market or used in the EU, or is its output used in the EU?',
    options: ['yes', 'no', 'not_sure'],
  }

  function asksEuLink(): ClassificationResult {
    return { ...decidedHighRisk(), follow_up_questions: [EU_LINK] }
  }

  it.each([
    ['used in the EU', { used_in: 'eu_and_outside' }],
    ['established in an EU country', { established_in: 'DE' }],
  ] as const)('pre-selects Yes for a company %s; it is sent only on a run', async (_, profile) => {
    inventories = [inventoryRow(profile)]
    const toolId = storeTool(asksEuLink())
    const user = await openTool(toolId)
    const panel = screen.getByRole('region', { name: 'Please confirm 1 fact' })
    const group = within(panel).getByRole('group', { name: EU_LINK.text })
    await expect
      .poll(() => within(group).getByRole('button', { name: 'Yes' }).getAttribute('aria-pressed'))
      .toBe('true')
    expect(panel).toHaveTextContent(
      'Filled in from your company profile. Please check it before you run the checks again.',
    )
    expect(classifyBodies).toEqual([])

    await user.click(within(panel).getByRole('button', { name: 'Add answer and run again' }))
    await expect.poll(() => classifyBodies.length).toBe(1)
    expect(classifyBodies[0]?.answers).toEqual({ eu_link: `${EU_LINK.text} Yes.` })
  })

  it('pre-selects nothing for a company established outside the EU', async () => {
    inventories = [inventoryRow({ established_in: 'US' })]
    const toolId = storeTool(asksEuLink())
    await openTool(toolId, 'de')
    const panel = screen.getByRole('region', { name: 'Bitte bestätigen Sie 1 Angabe' })
    const group = within(panel).getByRole('group', { name: EU_LINK.text })
    expect(within(group).getByRole('button', { name: 'Ja' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(
      within(panel).getByRole('button', { name: 'Antwort hinzufügen und erneut prüfen' }),
    ).toBeDisabled()
  })

  it('says where a pre-selected answer came from, in German', async () => {
    inventories = [inventoryRow({ used_in: 'eu' })]
    const toolId = storeTool(asksEuLink())
    await openTool(toolId, 'de')
    expect(
      await screen.findByText(
        'Aus Ihrem Unternehmensprofil übernommen. Bitte prüfen Sie es, bevor Sie die Prüfungen erneut starten.',
      ),
    ).toBeVisible()
  })
})
