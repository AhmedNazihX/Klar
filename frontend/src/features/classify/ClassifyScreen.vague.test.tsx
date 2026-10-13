// Classify with a description too thin to start (P20, E13, artboard `ClassifyVague`): the three
// prompts replace the fact questions, the checks wait, nothing is saved, and Run the checks runs
// again with the answers (decision 019). Supabase is configured, so a save would be seen.
import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassifyResponse } from '@/api'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import {
  CLASSIFY_URL,
  needsDescriptionEvents,
  sseBody,
  THIN_DESCRIPTION,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { SAVE_TOOL_URL, savedRunHandler } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import { inventoryRow, userDataHandlers } from '@/test/user-data-handlers'

import { clearDraft } from './classification-store'
import { DESCRIPTION_MAX } from './description-form'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

const SYSTEM_ID = '3b9d2f1e-6a4c-4e0b-8f3a-1c2d3e4f5a6b'
const CLASS_LABELS = ['Prohibited', 'High-risk', 'Limited risk', 'Minimal risk', 'Out of scope']

let requests: unknown[] = []
let saves: Record<string, unknown>[] = []

/** Streams the given runs in turn, one per request, and records each request's body. */
function classifyRuns(...runs: readonly ClassifyResponse[][]) {
  return http.post(CLASSIFY_URL, async ({ request }) => {
    requests.push(await request.json())
    const events = runs[Math.min(requests.length, runs.length) - 1] ?? []
    return new HttpResponse(sseBody(events), { headers: { 'Content-Type': 'text/event-stream' } })
  })
}

beforeEach(() => {
  clearDraft()
  requests = []
  saves = []
  server.use(
    ...userDataHandlers(
      () => [inventoryRow()],
      () => 0,
    ),
    http.post(SAVE_TOOL_URL, async ({ request }) => {
      saves.push((await request.json()) as Record<string, unknown>)
      return HttpResponse.json(SYSTEM_ID)
    }),
    savedRunHandler(),
  )
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

const TEXT = {
  en: {
    description: 'In your own words',
    run: 'Run the checks',
    title: 'Klar needs a little more to start',
    intro:
      'As described, it could be anything from a chatbot to a hiring tool, and the Act treats those very differently. Add a sentence or two on each of these:',
    footer: 'Add what you know. Klar asks for the rest.',
    waiting: 'Waiting for a description',
  },
  de: {
    description: 'In Ihren eigenen Worten',
    run: 'Prüfungen starten',
    title: 'Klar braucht etwas mehr, um zu starten',
    intro:
      'So beschrieben kann es alles sein, vom Chatbot bis zum Bewerbungstool, und die KI-Verordnung behandelt diese sehr unterschiedlich. Ergänzen Sie zu jedem Punkt ein, zwei Sätze:',
    footer: 'Ergänzen Sie, was Sie wissen. Klar fragt nach dem Rest.',
    waiting: 'Wartet auf eine Beschreibung',
  },
} as const

/** The three prompts and their hints, as the engine words them, in each language. */
const PROMPTS = {
  en: [
    [
      'What does it decide or suggest?',
      'For example: it ranks applicants, answers staff questions, plans shifts.',
    ],
    ['Who does it affect?', 'For example: applicants, your staff, customers.'],
    ['Did you buy it or build it?', 'And whether you changed it or put your own name on it.'],
  ],
  de: [
    [
      'Was entscheidet es oder was schlägt es vor?',
      'Zum Beispiel: Es reiht Bewerbungen, beantwortet Fragen von Beschäftigten, plant Schichten.',
    ],
    ['Wen betrifft es?', 'Zum Beispiel: Bewerbende, Ihre Beschäftigten, Kundschaft.'],
    [
      'Haben Sie es gekauft oder selbst entwickelt?',
      'Und ob Sie es verändert oder Ihren eigenen Namen daraufgesetzt haben.',
    ],
  ],
} as const

/** Opens Classify, describes the tool thinly and runs the checks; resolves once the prompts show. */
async function runThin(language: 'en' | 'de' = 'en', description: string = THIN_DESCRIPTION) {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  const rendered = renderRoute('/app/classify')
  await screen.findByRole('heading', { level: 1 })
  // A long description is pasted: typing it key by key would take minutes.
  await user.click(screen.getByLabelText(TEXT[language].description))
  await user.paste(description)
  await user.click(screen.getByRole('button', { name: TEXT[language].run }))
  const prompts = await screen.findByRole('region', { name: TEXT[language].title })
  return { user, prompts, ...rendered }
}

function expectNoClassAnywhere(): void {
  for (const label of CLASS_LABELS) {
    expect(screen.queryByText(new RegExp(`^${label}\\b`))).toBeNull()
  }
  expect(screen.queryByRole('region', { name: 'Result' })).toBeNull()
}

describe('Classify, a description too thin to start', () => {
  it('asks the three prompts in place of the fact questions, shows no class and saves nothing', async () => {
    server.use(classifyRuns(needsDescriptionEvents()))
    const { prompts, router } = await runThin()

    expect(within(prompts).getByText(TEXT.en.intro)).toBeVisible()
    expect(within(prompts).getByText(TEXT.en.footer)).toBeVisible()
    for (const [text, hint] of [
      [
        'What does it decide or suggest?',
        'For example: it ranks applicants, answers staff questions, plans shifts.',
      ],
      ['Who does it affect?', 'For example: applicants, your staff, customers.'],
      ['Did you buy it or build it?', 'And whether you changed it or put your own name on it.'],
    ] as const) {
      expect(within(prompts).getByRole('textbox', { name: text })).toBeEnabled()
      expect(within(prompts).getByText(hint)).toBeVisible()
    }
    // One Run the checks, under the prompts, and nothing new to run on yet.
    const runButtons = screen.getAllByRole('button', { name: 'Run the checks' })
    expect(runButtons).toHaveLength(1)
    expect(within(prompts).getByRole('button', { name: 'Run the checks' })).toBeDisabled()

    const panel = screen.getByRole('region', { name: "Checking in the Act's order" })
    expect(within(panel).getByText(TEXT.en.waiting)).toBeVisible()
    expect(within(panel).queryByRole('list')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expectNoClassAnywhere()
    expect(screen.getByLabelText('In your own words')).toHaveValue(THIN_DESCRIPTION)
    expect(router.state.location.pathname).toBe('/app/classify')
    expect(saves).toEqual([])
    expect(requests).toEqual([{ description: THIN_DESCRIPTION, language: 'en' }])
  })

  it('runs the checks again with the answers and keeps them in the saved description', async () => {
    server.use(classifyRuns(needsDescriptionEvents(), [...WORKED_EXAMPLE_EVENTS]))
    const { user, prompts, router } = await runThin()

    await user.type(
      within(prompts).getByRole('textbox', { name: 'What does it decide or suggest?' }),
      'It ranks job applicants for HR.',
    )
    await user.type(
      within(prompts).getByRole('textbox', { name: 'Who does it affect?' }),
      'People applying for jobs.',
    )
    await user.click(within(prompts).getByRole('button', { name: 'Run the checks' }))

    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${SYSTEM_ID}`)
    expect(requests).toEqual([
      { description: THIN_DESCRIPTION, language: 'en' },
      {
        description: THIN_DESCRIPTION,
        language: 'en',
        // A prompt left blank is not sent: the engine reads it as "don't know".
        answers: {
          what_it_decides: 'It ranks job applicants for HR.',
          who_it_affects: 'People applying for jobs.',
        },
      },
    ])
    expect(saves).toHaveLength(1)
    expect(saves[0]?.tool_description).toBe(
      `${THIN_DESCRIPTION}\n\nIt ranks job applicants for HR.\nPeople applying for jobs.`,
    )
  })

  it('runs again on a rewritten description without any answer', async () => {
    server.use(classifyRuns(needsDescriptionEvents(), needsDescriptionEvents()))
    const { user, prompts } = await runThin()
    const description = screen.getByLabelText('In your own words')

    await user.type(description, ' It ranks applicants.')
    const run = within(prompts).getByRole('button', { name: 'Run the checks' })
    expect(run).toBeEnabled()
    await user.click(run)

    await expect.poll(() => requests.length).toBe(2)
    expect(requests[1]).toEqual({
      description: `${THIN_DESCRIPTION} It ranks applicants.`,
      language: 'en',
    })
    // Still too thin: the prompts are asked again, and nothing is saved.
    expect(
      await screen.findByRole('region', { name: 'Klar needs a little more to start' }),
    ).toBeVisible()
    expect(saves).toEqual([])
  })

  it('asks the prompts in German', async () => {
    server.use(classifyRuns(needsDescriptionEvents('de')))
    const { prompts } = await runThin('de')

    expect(within(prompts).getByText(TEXT.de.intro)).toBeVisible()
    expect(within(prompts).getByText(TEXT.de.footer)).toBeVisible()
    expect(
      within(prompts).getByRole('textbox', { name: 'Was entscheidet es oder was schlägt es vor?' }),
    ).toBeVisible()
    expect(within(prompts).getByRole('textbox', { name: 'Wen betrifft es?' })).toBeVisible()
    expect(
      within(prompts).getByRole('textbox', {
        name: 'Haben Sie es gekauft oder selbst entwickelt?',
      }),
    ).toBeVisible()
    expect(within(prompts).getByRole('button', { name: 'Prüfungen starten' })).toBeDisabled()
    expect(screen.getByText(TEXT.de.waiting)).toBeVisible()
    expect(requests).toEqual([{ description: THIN_DESCRIPTION, language: 'de' }])
  })

  it.each([
    ['en', 'de'],
    ['de', 'en'],
  ] as const)(
    'keeps the prompts in one language after a switch from %s to %s',
    async (from, to) => {
      server.use(classifyRuns(needsDescriptionEvents(from)))
      const { prompts } = await runThin(from)

      await act(async () => {
        await i18n.changeLanguage(to)
      })

      expect(within(prompts).getByText(TEXT[to].title)).toBeVisible()
      for (const [text, hint] of PROMPTS[to]) {
        expect(within(prompts).getByRole('textbox', { name: text })).toBeVisible()
        expect(within(prompts).getByText(hint)).toBeVisible()
      }
      for (const [text, hint] of PROMPTS[from]) {
        expect(within(prompts).queryByText(text)).toBeNull()
        expect(within(prompts).queryByText(hint)).toBeNull()
      }
    },
  )

  it('lists the three prompts', async () => {
    server.use(classifyRuns(needsDescriptionEvents()))
    const { prompts } = await runThin()

    const list = within(prompts).getByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(3)
  })

  it('sends nothing on Enter in the name while there is nothing new to run on', async () => {
    server.use(classifyRuns(needsDescriptionEvents(), [...WORKED_EXAMPLE_EVENTS]))
    const { user, prompts } = await runThin()

    await user.type(screen.getByLabelText('What do you call the tool?'), 'HR helper{Enter}')
    // The one run that follows is the one the prompts' button starts, with the answer.
    await user.type(
      within(prompts).getByRole('textbox', { name: 'Who does it affect?' }),
      'People applying for jobs.',
    )
    await user.click(within(prompts).getByRole('button', { name: 'Run the checks' }))

    await expect.poll(() => saves.length).toBe(1)
    expect(requests).toEqual([
      { description: THIN_DESCRIPTION, language: 'en' },
      {
        description: THIN_DESCRIPTION,
        language: 'en',
        answers: { who_it_affects: 'People applying for jobs.' },
      },
    ])
  })

  it('saves a description near the limit whole, leaving out an answer that doesn’t fit', async () => {
    const answer = 'People applying for jobs.'
    const long = `We use AI for HR.${' It helps.'.repeat(1998)}`
    expect(long).toHaveLength(DESCRIPTION_MAX - 3)
    server.use(classifyRuns(needsDescriptionEvents(), [...WORKED_EXAMPLE_EVENTS]))
    const { user, prompts, router } = await runThin('en', long)

    await user.type(within(prompts).getByRole('textbox', { name: 'Who does it affect?' }), answer)
    await user.click(within(prompts).getByRole('button', { name: 'Run the checks' }))

    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${SYSTEM_ID}`)
    const saved = saves[0]?.tool_description
    // The answer whole would run past the limit, so it goes; never part of it.
    expect(`${long}\n\n${answer}`.length).toBeGreaterThan(DESCRIPTION_MAX)
    expect(saved).toBe(long)
  })

  it('passes axe', async () => {
    server.use(classifyRuns(needsDescriptionEvents()))
    const { container } = await runThin()
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})
