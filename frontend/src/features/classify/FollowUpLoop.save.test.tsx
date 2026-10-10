// The follow-up loop with Supabase configured (P5b, P19): a re-run is saved as the tool's next
// run with the answers it used, a stored tool shows what its last answer changed, Undo answer
// deletes the latest run by its row id, a run or undo that outlives its session is dropped, and
// the company profile pre-selects the EU answer (decision 026 item 2).
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { QueryClient } from '@tanstack/react-query'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ClassificationResult, ClassifyRequest, FollowUpQuestion } from '@/api'
import {
  endAnonymousSession,
  heldSessionId,
  withAnonymousSession,
} from '@/hooks/use-anonymous-session'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import {
  ANNEX_III_QUESTION,
  annexIIINeedsInfo,
  CLASSIFY_URL,
  classifyHandler,
  decidedHighRisk,
  minimalRisk,
  sseBody,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { CLASSIFICATIONS_URL, toolRow } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { SIGNUP_URL } from '@/test/supabase-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { inventoryRow, userDataHandlers } from '@/test/user-data-handlers'

import { putRun } from './classification-store'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

const ANSWER = `${ANNEX_III_QUESTION} No.`
const RUN_1 = '0a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c01'
const RUN_2 = '0a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c02'

type Row = Record<string, unknown>

let inventories: Row[] = []
let tools: Row[] = []
/** The tool's classifications rows, as the table holds them. */
let runs: Row[] = []
let inserts: Row[] = []
/** Each delete's filter on the row id ("eq.<id>"). */
let deletes: (string | null)[] = []
let classifyBodies: ClassifyRequest[] = []
let signups = 0

/** PostgREST for classifications: reads newest first, inserts numbered as the database does (the
 *  highest number plus one, so a deleted run's number comes back), and deletes by row id,
 *  answering with the rows deleted. */
function classificationsHandlers(insertError: { status: number; code: string } | null = null) {
  return [
    http.get(CLASSIFICATIONS_URL, ({ request }) => {
      const limit = Number(new URL(request.url).searchParams.get('limit') ?? '2')
      const newest = [...runs].sort((a, b) => Number(b['run_no']) - Number(a['run_no']))
      return HttpResponse.json(newest.slice(0, limit))
    }),
    http.post(CLASSIFICATIONS_URL, async ({ request }) => {
      const row = (await request.json()) as Row
      inserts.push(row)
      if (insertError) {
        return HttpResponse.json(
          { code: insertError.code, message: 'refused' },
          { status: insertError.status },
        )
      }
      const runNo = Math.max(0, ...runs.map((run) => Number(run['run_no']))) + 1
      const id = crypto.randomUUID()
      runs.push({ ...row, id, run_no: runNo })
      return HttpResponse.json({ id, run_no: runNo }, { status: 201 })
    }),
    http.delete(CLASSIFICATIONS_URL, ({ request }) => {
      const filter = new URL(request.url).searchParams.get('id')
      deletes.push(filter)
      const deleted = runs.filter((run) => `eq.${String(run['id'])}` === filter)
      runs = runs.filter((run) => !deleted.includes(run))
      return HttpResponse.json(deleted.map((run) => ({ id: run['id'] })))
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
  signups = 0
  server.use(
    // Counts each sign-in, then falls through to the handler that answers it.
    http.post(SIGNUP_URL, () => {
      signups += 1
    }),
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

/** The stored tool's first run, as the classifications table holds it. */
function firstRun(result: ClassificationResult = annexIIINeedsInfo()): Row {
  return { id: RUN_1, run_no: 1, result, inputs: null }
}

async function openTool(
  toolId: string,
  language: 'en' | 'de' = 'en',
): Promise<{ user: ReturnType<typeof userEvent.setup>; client: QueryClient }> {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  const client = createTestQueryClient()
  renderRoute(`/app/inventory/${toolId}`, client)
  await screen.findByRole('heading', { level: 1, name: 'Shift planner' })
  return { user, client }
}

async function answerNo(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
  await user.click(within(question).getByRole('button', { name: 'No' }))
  await user.click(within(question).getByRole('button', { name: 'Add answer and run again' }))
}

/** A response held until `release` is called. */
function holdUntilReleased(): { gate: Promise<void>; release: () => void } {
  let release = (): void => undefined
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  return {
    gate,
    release: () => {
      release()
    },
  }
}

describe('Saving a follow-up run', () => {
  it("adds the re-run as the tool's next run, with the answers beside the description", async () => {
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [firstRun()]
    const { user } = await openTool(toolId)
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

  it('Undo answer deletes the re-run by its row id and shows the run before', async () => {
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [firstRun()]
    const { user } = await openTool(toolId)
    await answerNo(user)
    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    const added = String(runs[1]?.['id'])

    await user.click(within(banner).getByRole('button', { name: 'Undo answer' }))
    expect(await screen.findByRole('region', { name: ANNEX_III_QUESTION })).toBeVisible()
    expect(deletes).toEqual([`eq.${added}`])
    expect(runs.map((run) => run['id'])).toEqual([RUN_1])
  })

  it('an undo of a run already gone shows the tool as it is now, not the run before', async () => {
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [firstRun()]
    const { user } = await openTool(toolId)
    await answerNo(user)
    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    // Another tab undid the answer and ran the tool again: its run 2 is a newer, paid run that
    // reuses the number of the one shown here.
    const newer = { id: RUN_2, run_no: 2, result: decidedHighRisk(), inputs: null }
    runs = [firstRun(), newer]
    tools = [{ ...tools[0], run_no: 2, result: decidedHighRisk() }]

    await user.click(within(banner).getByRole('button', { name: 'Undo answer' }))
    await waitFor(() => {
      expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
    })
    // Nothing of the other tab's was deleted, and the run before isn't shown as the latest.
    expect(runs.map((run) => run['id'])).toEqual([RUN_1, RUN_2])
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('High-risk')).toBeInTheDocument()
    expect(within(summary).getByText('Decided')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: ANNEX_III_QUESTION })).toBeNull()
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
      const { user } = await openTool(toolId, language)
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

  it("numbers the re-run as the database saved it, not the shown run's number plus one", async () => {
    server.use(
      http.post(CLASSIFICATIONS_URL, async ({ request }) => {
        inserts.push((await request.json()) as Row)
        return HttpResponse.json({ id: RUN_2, run_no: 5 }, { status: 201 })
      }),
    )
    const toolId = storeTool(annexIIINeedsInfo(), 3)
    runs = [{ ...firstRun(), run_no: 3 }]
    const { user } = await openTool(toolId)
    await answerNo(user)

    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    expect(banner).toHaveTextContent('Run 5 of 5')
    expect(
      screen.getByRole('heading', { level: 2, name: 'Run 5: how Klar got here' }),
    ).toBeVisible()
  })

  it('an undo of a run whose row id is unknown reads the tool again, deleting nothing', async () => {
    // The tool's latest run, as another tab left it.
    const toolId = storeTool(decidedHighRisk(), 2)
    runs = [firstRun(), { id: RUN_2, run_no: 2, result: decidedHighRisk(), inputs: null }]
    await i18n.changeLanguage('en')
    const user = userEvent.setup()
    const client = createTestQueryClient()
    putRun(client, {
      toolId,
      name: 'Shift planner',
      description: 'd',
      result: minimalRisk(),
      runNo: 2,
      answers: { used_for_recruitment: ANSWER },
      previous: { runNo: 1, result: annexIIINeedsInfo(), answers: {} },
    })
    renderRoute(`/app/inventory/${toolId}`, client)
    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    await expect.poll(() => heldSessionId(client)).not.toBeNull()

    await user.click(within(banner).getByRole('button', { name: 'Undo answer' }))
    await waitFor(() => {
      expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
    })
    expect(deletes).toEqual([])
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('High-risk')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: ANNEX_III_QUESTION })).toBeNull()
  })

  it('a re-run the inventory refuses still shows, with a note that it was not saved', async () => {
    server.use(...classificationsHandlers({ status: 400, code: 'PT507' }))
    const toolId = storeTool(annexIIINeedsInfo())
    const { user } = await openTool(toolId)
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

describe('A re-run or an undo that outlives its session (sign-out, Delete my data)', () => {
  it('drops a re-run that finishes after the session ended: nothing saved or shown', async () => {
    const held = holdUntilReleased()
    server.use(
      http.post(CLASSIFY_URL, async ({ request }) => {
        classifyBodies.push((await request.json()) as ClassifyRequest)
        await held.gate
        return new HttpResponse(sseBody([{ event: 'result', result: minimalRisk() }]), {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
    )
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [firstRun()]
    const { user, client } = await openTool(toolId)
    const signupsBefore = signups
    await answerNo(user)
    await expect.poll(() => classifyBodies.length).toBe(1)

    endAnonymousSession(client)
    held.release()
    await waitFor(() => {
      expect(screen.queryByRole('region', { name: "Checking in the Act's order" })).toBeNull()
    })
    expect(inserts).toEqual([])
    expect(signups).toBe(signupsBefore)
    expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
    expect(screen.getByRole('region', { name: ANNEX_III_QUESTION })).toBeVisible()
  })

  it('drops a re-run whose session ends while it is being saved: nothing shown, no sign-in', async () => {
    const held = holdUntilReleased()
    server.use(
      http.post(CLASSIFICATIONS_URL, async ({ request }) => {
        inserts.push((await request.json()) as Row)
        await held.gate
        return HttpResponse.json({ id: RUN_2, run_no: 2 }, { status: 201 })
      }),
    )
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [firstRun()]
    const { user, client } = await openTool(toolId)
    const signupsBefore = signups
    await answerNo(user)
    await expect.poll(() => inserts.length).toBe(1)

    endAnonymousSession(client)
    held.release()
    await waitFor(() => {
      expect(screen.queryByRole('region', { name: "Checking in the Act's order" })).toBeNull()
    })
    expect(signups).toBe(signupsBefore)
    expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
    expect(screen.getByRole('region', { name: ANNEX_III_QUESTION })).toBeVisible()
  })

  it('a re-run started with no session on a saved tool saves nothing and signs nobody in', async () => {
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [firstRun()]
    const { user, client } = await openTool(toolId)
    endAnonymousSession(client)
    const signupsBefore = signups
    await answerNo(user)
    await expect.poll(() => classifyBodies.length).toBe(1)

    await waitFor(() => {
      expect(screen.queryByRole('region', { name: "Checking in the Act's order" })).toBeNull()
    })
    expect(inserts).toEqual([])
    expect(signups).toBe(signupsBefore)
    expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
    expect(screen.getByRole('region', { name: ANNEX_III_QUESTION })).toBeVisible()
  })

  it('an undo started with no session on a saved tool deletes nothing and signs nobody in', async () => {
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [firstRun()]
    const { user, client } = await openTool(toolId)
    await answerNo(user)
    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    endAnonymousSession(client)
    const signupsBefore = signups

    const undo = within(banner).getByRole('button', { name: 'Undo answer' })
    await user.click(undo)
    await waitFor(() => {
      expect(undo).toBeEnabled()
    })
    expect(deletes).toEqual([])
    expect(signups).toBe(signupsBefore)
    expect(screen.getByRole('region', { name: 'Your answer changed the result.' })).toBeVisible()
    expect(screen.queryByRole('region', { name: ANNEX_III_QUESTION })).toBeNull()
  })

  it('shows a re-run of an unsaved tool started with no session when one starts meanwhile', async () => {
    const held = holdUntilReleased()
    server.use(
      http.post(CLASSIFY_URL, async ({ request }) => {
        classifyBodies.push((await request.json()) as ClassifyRequest)
        await held.gate
        return new HttpResponse(sseBody([{ event: 'result', result: minimalRisk() }]), {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
    )
    await i18n.changeLanguage('en')
    const user = userEvent.setup()
    const client = createTestQueryClient()
    // A fresh run the inventory couldn't save: it lives only in this tab.
    putRun(client, {
      toolId: 'unsaved-tool',
      name: 'Shift planner',
      description: 'd',
      result: annexIIINeedsInfo(),
      saveFailure: 'failed',
    })
    renderRoute('/app/inventory/unsaved-tool', client)
    await screen.findByRole('heading', { level: 1, name: 'Shift planner' })
    await expect.poll(() => heldSessionId(client)).not.toBeNull()
    endAnonymousSession(client)
    await answerNo(user)
    await expect.poll(() => classifyBodies.length).toBe(1)

    // Another screen's read starts a session while the run streams.
    await withAnonymousSession(client, supabase)
    expect(heldSessionId(client)).not.toBeNull()
    held.release()
    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    expect(banner).toHaveTextContent('Run 2 of 2')
    expect(inserts).toEqual([])
  })

  it('keeps the run before off the screen when the session ends during an undo', async () => {
    const toolId = storeTool(annexIIINeedsInfo())
    runs = [firstRun()]
    const { user, client } = await openTool(toolId)
    await answerNo(user)
    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    const held = holdUntilReleased()
    server.use(
      http.delete(CLASSIFICATIONS_URL, async ({ request }) => {
        deletes.push(new URL(request.url).searchParams.get('id'))
        await held.gate
        return HttpResponse.json([{ id: runs[1]?.['id'] }])
      }),
    )

    const undo = within(banner).getByRole('button', { name: 'Undo answer' })
    await user.click(undo)
    await expect.poll(() => deletes.length).toBe(1)
    endAnonymousSession(client)
    held.release()
    await waitFor(() => {
      expect(undo).toBeEnabled()
    })
    expect(screen.getByRole('region', { name: 'Your answer changed the result.' })).toBeVisible()
    expect(screen.queryByRole('region', { name: ANNEX_III_QUESTION })).toBeNull()
  })
})

describe('A stored tool after an answer', () => {
  it('shows what its last answer changed, read from its last two runs', async () => {
    const toolId = storeTool(minimalRisk(), 2)
    runs = [
      { id: RUN_1, run_no: 1, result: annexIIINeedsInfo(), inputs: { description: 'd' } },
      {
        id: RUN_2,
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
    // Given in English, read on a German screen: the choice in German.
    expect(banner).toHaveTextContent(`Sie haben auf „${ANNEX_III_QUESTION}“ mit „Nein“ geantwortet`)
  })

  it.each([
    ['an edited description', { description: 'edited', answers: {} }],
    ['a run stored before P19 (no inputs)', null],
    ['inputs Klar cannot read', { answers: 'not a map' }],
  ])('shows no change for a second run from %s', async (_, inputs) => {
    const toolId = storeTool(minimalRisk(), 2)
    runs = [firstRun(), { id: RUN_2, run_no: 2, result: minimalRisk(), inputs }]
    await openTool(toolId)
    // The stored result still shows; only the banner of an answer's re-run is left out.
    expect(
      within(screen.getByRole('region', { name: 'Result' })).getByText('Minimal risk'),
    ).toBeVisible()
    expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
  })

  it('still shows the result when its last two runs cannot be read', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    server.use(
      http.get(CLASSIFICATIONS_URL, () =>
        HttpResponse.json({ code: '57014', message: 'canceling statement' }, { status: 500 }),
      ),
    )
    const toolId = storeTool(minimalRisk(), 2)
    await openTool(toolId)
    expect(
      within(screen.getByRole('region', { name: 'Result' })).getByText('Minimal risk'),
    ).toBeVisible()
    expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    // Logged with its code only: no user text reaches the console.
    expect(warn).toHaveBeenCalledWith("Klar couldn't read the tool's last two runs.", '57014')
    warn.mockRestore()
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
    const { user } = await openTool(toolId)
    const panel = screen.getByRole('region', { name: '1 open question' })
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
    const panel = screen.getByRole('region', { name: '1 offene Frage' })
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

  it.each([
    ['en', 'Confirm', 'Confirmed: HR reviews every shortlist.'],
    ['de', 'Bestätigen', 'Bestätigt: HR reviews every shortlist.'],
  ] as const)(
    'Confirm on a fact card sends only that fact with the run, not the pre-filled answer (%s)',
    async (language, confirm, line) => {
      inventories = [inventoryRow({ used_in: 'eu' })]
      const result: ClassificationResult = {
        ...asksEuLink(),
        deciding_facts: [{ text: 'HR reviews every shortlist.', evidence: 'assumed' }],
      }
      const toolId = storeTool(result, 2)
      const earlier = { human_review: 'HR reads every one.' }
      runs = [
        firstRun(),
        { id: RUN_2, run_no: 2, result, inputs: { description: 'd', answers: earlier } },
      ]
      const { user } = await openTool(toolId, language)
      const panel = screen.getByRole('region', { name: /^1 (open question|offene Frage)$/ })
      await expect
        .poll(() => within(panel).getAllByRole('button', { pressed: true }).length)
        .toBe(1)

      const facts = screen.getByRole('complementary', {
        name: language === 'en' ? 'The result rests on' : 'Das Ergebnis beruht auf',
      })
      await user.click(within(facts).getByRole('button', { name: confirm }))
      await expect.poll(() => classifyBodies.length).toBe(1)
      expect(classifyBodies[0]?.answers).toEqual({ ...earlier, confirmed_fact_1: line })
    },
  )
})
