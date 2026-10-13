// The follow-up loop on a result (P5b; artboards `ResultNeedsInfo`, `ResultRerun`, `Classify`):
// answering re-runs the engine with the answers next to the description, the re-run result shows
// with what it changed, and Undo answer brings the run before back. Without Supabase, as in the
// other result tests: nothing is saved (FollowUpLoop.save.test.tsx covers the saving).
import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import type {
  ClassificationResult,
  ClassifyRequest,
  ClassifyResponse,
  FollowUpQuestion,
} from '@/api'
import {
  ANNEX_III_QUESTION,
  annexIIINeedsInfo,
  CLASSIFY_URL,
  classifyHandler,
  decidedHighRisk,
  minimalRisk,
  WORKED_EXAMPLE,
  WORKED_EXAMPLE_DESCRIPTION,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { openQuestionCount } from '@/features/inventory/tool-facts'
import { server } from '@/test/msw-server'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { putRun, type ClassificationRun } from './classification-store'
import { uniqueFacts } from './result-text'

const TOOL_ID = 'applicant-screening'
// Axe can't compute contrast over glass in jsdom (AppFrame.test.tsx does the same).
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }

/** The recorded stream with `result` as its last event. */
function eventsEndingWith(result: ClassificationResult): ClassifyResponse[] {
  return [...WORKED_EXAMPLE_EVENTS.slice(0, -1), { event: 'result', result }]
}

/** Streams `result` for every classify request, and keeps each request's body. */
function rerunReturns(result: ClassificationResult): ClassifyRequest[] {
  const bodies: ClassifyRequest[] = []
  server.use(
    classifyHandler(eventsEndingWith(result), (body) => {
      bodies.push(body as ClassifyRequest)
    }),
  )
  return bodies
}

async function openResult(
  result: ClassificationResult,
  { language = 'en', run = {} }: { language?: 'en' | 'de'; run?: Partial<ClassificationRun> } = {},
) {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  putRun(client, {
    toolId: TOOL_ID,
    name: 'Applicant screening',
    description: WORKED_EXAMPLE_DESCRIPTION,
    result,
    ...run,
  })
  const { container } = renderRoute(`/app/inventory/${TOOL_ID}`, client)
  await screen.findByRole('heading', { level: 1, name: 'Applicant screening' })
  return { user: userEvent.setup(), container }
}

function stepRow(name: RegExp): HTMLElement {
  const section = screen.getByRole('region', {
    name: /how Klar got here|wie Klar zum Ergebnis kam|where the checks stand|Stand der Prüfungen/i,
  })
  return within(section).getByRole('button', { name })
}

describe('Answering the question that decides a result', () => {
  it('re-runs with the answer next to the description and shows the re-run result', async () => {
    const bodies = rerunReturns(minimalRisk())
    const { user } = await openResult(annexIIINeedsInfo())
    const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
    const runAgain = within(question).getByRole('button', { name: 'Add answer and run again' })
    expect(runAgain).toBeDisabled()

    await user.click(within(question).getByRole('button', { name: 'No' }))
    expect(within(question).getByRole('button', { name: 'No' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await user.click(runAgain)

    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })
    // The description stays the user's own; the answer goes beside it (decision 019).
    expect(bodies).toEqual([
      {
        description: WORKED_EXAMPLE_DESCRIPTION,
        language: 'en',
        answers: { used_for_recruitment: `${ANNEX_III_QUESTION} No.` },
      },
    ])
    expect(banner).toHaveTextContent('Run 2 of 2')
    // The answer as the user gave it, not the line the engine read.
    expect(banner).toHaveTextContent(`You said “No” to “${ANNEX_III_QUESTION}”`)
    expect(banner).not.toHaveTextContent(`${ANNEX_III_QUESTION} No.`)
    expect(within(banner).getByText('High-risk, assumed')).toBeInTheDocument()
    expect(within(banner).getByText('Minimal risk')).toBeInTheDocument()
    // The re-run result is the one shown, and the question is gone.
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('Minimal risk')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: ANNEX_III_QUESTION })).toBeNull()
    expect(stepRow(/^3 High-risk/)).toHaveTextContent('Changed: Not high-risk')
    expect(stepRow(/^1 Scope/)).not.toHaveTextContent('Changed')
    expect(
      screen.getByRole('heading', { level: 2, name: 'Run 2: how Klar got here' }),
    ).toBeVisible()
  })

  it.each([
    ['en', 'No', 'Add answer and run again', 'Run 2: where the checks stand'],
    ['de', 'Nein', 'Antwort hinzufügen und erneut prüfen', 'Durchlauf 2: Stand der Prüfungen'],
  ] as const)(
    'names the run and where the checks stand when the re-run still waits (%s)',
    async (language, no, runAgainName, heading) => {
      rerunReturns(annexIIINeedsInfo())
      const { user } = await openResult(annexIIINeedsInfo(), { language })
      const [question] = screen.getAllByRole('region', { name: /\?$/ })
      if (!question) throw new Error('The paused result asks no question.')
      await user.click(within(question).getByRole('button', { name: no }))
      await user.click(within(question).getByRole('button', { name: runAgainName }))
      expect(await screen.findByRole('heading', { level: 2, name: heading })).toBeVisible()
    },
  )

  it('lists what changed in the inventory, obligations and needs-you lists', async () => {
    rerunReturns(minimalRisk())
    const { user } = await openResult(annexIIINeedsInfo())
    const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
    await user.click(within(question).getByRole('button', { name: 'No' }))
    await user.click(within(question).getByRole('button', { name: 'Add answer and run again' }))

    const lists = await screen.findByRole('region', { name: 'What changed in your lists' })
    const rows = within(lists).getAllByRole('definition')
    expect(rows.map((row) => row.textContent)).toEqual([
      'High-risk, assumed→changed toMinimal risk',
      expect.stringMatching(/^\d+ possible duties→changed to1 duty$/),
      'Answer 1 question to finish the check→changed toNothing to do',
    ])
  })

  it('never sends Not sure: the run waits for an answer it can send', async () => {
    const bodies = rerunReturns(minimalRisk())
    const { user } = await openResult(annexIIINeedsInfo())
    const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
    await user.click(within(question).getByRole('button', { name: 'Not sure' }))
    expect(
      within(question).getByRole('button', { name: 'Add answer and run again' }),
    ).toBeDisabled()
    expect(within(question).getByText('Not sure? Ask your vendor:')).toBeInTheDocument()
    expect(within(question).getByText(`“${ANNEX_III_QUESTION}”`)).toBeInTheDocument()
    expect(bodies).toEqual([])
  })

  it('sends an answer in words for a question without options', async () => {
    // The recorded worked example pauses at scope on the Art. 3(1) question, answered in words.
    const bodies = rerunReturns(decidedHighRisk())
    const { user } = await openResult(WORKED_EXAMPLE)
    const asked = WORKED_EXAMPLE.steps.find((step) => step.step === 'scope')?.missing_fact
    if (!asked) throw new Error('The recorded result pauses at scope.')
    const question = screen.getByRole('region', { name: asked.text })
    await user.type(
      within(question).getByRole('textbox', { name: asked.text }),
      '  It is a model trained on past hiring data.  ',
    )
    // The worked example asks more questions: the one run action sits under the last panel.
    await user.click(screen.getByRole('button', { name: 'Add answers and run again' }))

    await screen.findByRole('region', { name: 'Your answer changed the result.' })
    expect(bodies[0]?.answers).toEqual({ ai_system: 'It is a model trained on past hiring data.' })
  })

  it('Undo answer brings back the run before, with its question', async () => {
    rerunReturns(minimalRisk())
    const { user } = await openResult(annexIIINeedsInfo())
    const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
    await user.click(within(question).getByRole('button', { name: 'No' }))
    await user.click(within(question).getByRole('button', { name: 'Add answer and run again' }))
    const banner = await screen.findByRole('region', { name: 'Your answer changed the result.' })

    await user.click(within(banner).getByRole('button', { name: 'Undo answer' }))
    const back = await screen.findByRole('region', { name: ANNEX_III_QUESTION })
    expect(within(back).getByRole('button', { name: 'No' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.queryByRole('region', { name: 'Your answer changed the result.' })).toBeNull()
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('Needs more information')).toBeInTheDocument()
  })

  it.each([
    [
      'en',
      'Yes',
      'Add answer and run again',
      "Your answer didn't change the class.",
      'Klar ran every check again with your answer added to the description.',
    ],
    [
      'de',
      'Ja',
      'Antwort hinzufügen und erneut prüfen',
      'Ihre Antwort hat die Einstufung nicht geändert.',
      'Klar hat alle Prüfungen erneut durchgeführt, mit Ihrer Antwort als Teil der Beschreibung.',
    ],
  ] as const)(
    'says so when the answer leaves the class as it was (%s)',
    async (language, yes, runAgain, title, body) => {
      rerunReturns(annexIIINeedsInfo())
      const { user } = await openResult(annexIIINeedsInfo(), { language })
      const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
      await user.click(within(question).getByRole('button', { name: yes }))
      await user.click(within(question).getByRole('button', { name: runAgain }))
      expect(await screen.findByRole('region', { name: title })).toHaveTextContent(body)
    },
  )

  it.each([
    ['en', 'Copy question', 'Question copied.'],
    ['de', 'Frage kopieren', 'Frage kopiert.'],
  ] as const)('copies the vendor question (%s)', async (language, copy, copied) => {
    const { user } = await openResult(annexIIINeedsInfo(), { language })
    const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
    await user.click(within(question).getByRole('button', { name: copy }))
    expect(await within(question).findByRole('status')).toHaveTextContent(copied)
    expect(await navigator.clipboard.readText()).toBe(ANNEX_III_QUESTION)
  })

  it.each([
    [
      'en',
      'Yes',
      'Add answer and run again',
      'Try again',
      'Your earlier result still stands',
      'Your answers are kept. Try again to run the checks with them.',
      "The checks couldn't finish",
      'Nothing is lost',
    ],
    [
      'de',
      'Ja',
      'Antwort hinzufügen und erneut prüfen',
      'Erneut versuchen',
      'Ihr bisheriges Ergebnis gilt weiter',
      'Ihre Antworten bleiben erhalten. Versuchen Sie es erneut, um die Prüfungen damit durchzuführen.',
      'Die Prüfungen konnten nicht abgeschlossen werden',
      'Nichts geht verloren',
    ],
  ] as const)(
    'a failed re-run says the result shown stands and the answers are kept; Try again sends them once (%s)',
    async (language, yes, runAgain, tryAgain, title, body, firstRunTitle, firstRunBody) => {
      const bodies: unknown[] = []
      server.use(
        http.post(CLASSIFY_URL, async ({ request }) => {
          bodies.push(await request.json())
          return HttpResponse.json({ detail: 'busy' }, { status: 503 })
        }),
      )
      const { user } = await openResult(annexIIINeedsInfo(), { language })
      const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
      await user.click(within(question).getByRole('button', { name: yes }))
      await user.click(within(question).getByRole('button', { name: runAgain }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(title)
      expect(alert).toHaveTextContent(body)
      // Not the Classify screen's words, which say there is no result yet.
      expect(alert).not.toHaveTextContent(firstRunTitle)
      expect(alert).not.toHaveTextContent(firstRunBody)
      // No class from a failed run: the result shown is still the one before.
      expect(screen.queryByRole('region', { name: /Your answer|Ihre Antwort/ })).toBeNull()
      expect(bodies).toHaveLength(1)

      await user.click(within(alert).getByRole('button', { name: tryAgain }))
      await expect.poll(() => bodies.length).toBe(2)
      expect(bodies[1]).toEqual(bodies[0])
      expect(bodies[1]).toMatchObject({
        answers: { used_for_recruitment: `${ANNEX_III_QUESTION} ${yes}.` },
      })
    },
  )

  it.each([
    [
      'en',
      'Yes',
      'Add answer and run again',
      'The service answered with an error (HTTP 500).',
      "The checks couldn't start",
    ],
    [
      'de',
      'Ja',
      'Antwort hinzufügen und erneut prüfen',
      'Der Dienst hat mit einem Fehler geantwortet (HTTP 500).',
      'Die Prüfungen konnten nicht starten',
    ],
  ] as const)(
    'a failed re-run says why once, in the re-run alert only (%s)',
    async (language, yes, runAgain, reason, notStarted) => {
      server.use(http.post(CLASSIFY_URL, () => HttpResponse.json({}, { status: 500 })))
      const { user } = await openResult(annexIIINeedsInfo(), { language })
      const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
      await user.click(within(question).getByRole('button', { name: yes }))
      await user.click(within(question).getByRole('button', { name: runAgain }))

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(reason)
      expect(screen.getAllByText(reason)).toHaveLength(1)
      expect(screen.queryByText(notStarted)).toBeNull()
    },
  )

  it('passes axe after an answer', async () => {
    rerunReturns(minimalRisk())
    const { user, container } = await openResult(annexIIINeedsInfo())
    const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
    await user.click(within(question).getByRole('button', { name: 'No' }))
    await user.click(within(question).getByRole('button', { name: 'Add answer and run again' }))
    await screen.findByRole('region', { name: 'Your answer changed the result.' })
    const results = await axe(container, AXE_OPTIONS)
    expect(results.violations).toEqual([])
  })
})

describe('Answering in German', () => {
  it('sends the German answer and shows the change in German', async () => {
    const bodies = rerunReturns(minimalRisk())
    const { user } = await openResult(annexIIINeedsInfo(), { language: 'de' })
    const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
    expect(within(question).getByText('Nicht sicher? Fragen Sie Ihren Anbieter:')).toBeVisible()
    expect(within(question).getByRole('button', { name: 'Frage kopieren' })).toBeVisible()
    await user.click(within(question).getByRole('button', { name: 'Nein' }))
    await user.click(
      within(question).getByRole('button', { name: 'Antwort hinzufügen und erneut prüfen' }),
    )

    const banner = await screen.findByRole('region', {
      name: 'Ihre Antwort hat das Ergebnis geändert.',
    })
    expect(bodies[0]).toMatchObject({
      language: 'de',
      answers: { used_for_recruitment: `${ANNEX_III_QUESTION} Nein.` },
    })
    expect(banner).toHaveTextContent('Durchlauf 2 von 2')
    expect(banner).toHaveTextContent(`Sie haben auf „${ANNEX_III_QUESTION}“ mit „Nein“ geantwortet`)
    expect(within(banner).getByRole('button', { name: 'Antwort rückgängig machen' })).toBeVisible()
    const lists = screen.getByRole('region', { name: 'Was sich in Ihren Listen geändert hat' })
    expect(within(lists).getAllByRole('definition')[2]).toHaveTextContent(
      'Beantworten Sie 1 Frage, um die Prüfung abzuschließen→geändert zuNichts zu tun',
    )
    expect(stepRow(/^3 Hochrisiko/)).toHaveTextContent('Geändert: ')
    expect(
      screen.getByRole('heading', { level: 2, name: 'Durchlauf 2: wie Klar zum Ergebnis kam' }),
    ).toBeVisible()
  })
})

describe('An answer read on a screen in the other language', () => {
  it.each([
    ['de', 'Nein', 'Antwort hinzufügen und erneut prüfen', 'en', `You said “No” to`],
    ['en', 'No', 'Add answer and run again', 'de', 'mit „Nein“ geantwortet'],
  ] as const)(
    'shows a choice made in %s in the screen’s language now',
    async (given, no, runAgain, shown, said) => {
      rerunReturns(minimalRisk())
      const { user } = await openResult(annexIIINeedsInfo(), { language: given })
      const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
      await user.click(within(question).getByRole('button', { name: no }))
      await user.click(within(question).getByRole('button', { name: runAgain }))
      await screen.findByRole('region', { name: /Your answer|Ihre Antwort/ })

      await act(() => i18n.changeLanguage(shown))
      const banner = screen.getByRole('region', { name: /Your answer|Ihre Antwort/ })
      expect(banner).toHaveTextContent(said)
      expect(banner).not.toHaveTextContent(`“${no}”`)
      expect(banner).not.toHaveTextContent(`„${no}“`)
    },
  )

  it('keeps an answer in words as the user typed it', async () => {
    const asked = WORKED_EXAMPLE.steps.find((step) => step.step === 'scope')?.missing_fact
    if (!asked) throw new Error('The recorded result pauses at scope.')
    rerunReturns(decidedHighRisk())
    const { user } = await openResult(WORKED_EXAMPLE, { language: 'de' })
    const question = screen.getByRole('region', { name: asked.text })
    await user.type(within(question).getByRole('textbox', { name: asked.text }), 'Nein')
    await user.click(screen.getByRole('button', { name: 'Antworten hinzufügen und erneut prüfen' }))
    await screen.findByRole('region', { name: /Ihre Antwort/ })

    await act(() => i18n.changeLanguage('en'))
    expect(screen.getByRole('region', { name: /Your answer/ })).toHaveTextContent(
      `You said “Nein” to “${asked.text}”`,
    )
  })
})

describe('The open questions panel', () => {
  const legacyQuestion: FollowUpQuestion = {
    id: 'significant_design_change',
    text: "Is a significant change to the system's design or intended purpose planned or foreseen?",
    hint: 'Decides whether Art. 111(2) limits the high-risk duties.',
    options: ['yes', 'no', 'not_sure'],
  }
  const wordsQuestion: FollowUpQuestion = {
    id: 'human_review',
    text: 'Does a person review the shortlist before it affects hiring decisions?',
    options: [],
  }

  function withQuestions(): ClassificationResult {
    return { ...decidedHighRisk(), follow_up_questions: [legacyQuestion, wordsQuestion] }
  }

  it.each([
    [
      'en',
      '2 open questions',
      "Klar couldn't settle these from the description. Your answers can change the result.",
      'No',
      'No.',
    ],
    [
      'de',
      '2 offene Fragen',
      'Klar konnte diese nicht aus der Beschreibung klären. Ihre Antworten können das Ergebnis ändern.',
      'Nein',
      'Nein.',
    ],
  ] as const)(
    'asks every follow-up question and sends the answers given (%s)',
    async (language, heading, intro, no, said) => {
      const bodies = rerunReturns(decidedHighRisk())
      const { user } = await openResult(withQuestions(), { language })
      const panel = screen.getByRole('region', { name: heading })
      expect(panel).toHaveTextContent(intro)
      expect(panel).toHaveTextContent(legacyQuestion.hint ?? '')
      await user.click(
        within(within(panel).getByRole('group', { name: legacyQuestion.text })).getByRole(
          'button',
          { name: no },
        ),
      )
      await user.type(
        within(panel).getByRole('textbox', { name: wordsQuestion.text }),
        'HR reads every one.',
      )
      await user.click(within(panel).getAllByRole('button').at(-1) as HTMLElement)

      await expect.poll(() => bodies.length).toBe(1)
      expect(bodies[0]?.answers).toEqual({
        significant_design_change: `${legacyQuestion.text} ${said}`,
        human_review: 'HR reads every one.',
      })
    },
  )

  it('keeps the answers an earlier run used, so the engine reads them all', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const earlier = { eu_link: 'Is the system used in the EU? Yes.' }
    const { user } = await openResult(withQuestions(), {
      run: { runNo: 2, answers: earlier },
    })
    const panel = screen.getByRole('region', { name: '2 open questions' })
    await user.click(
      within(within(panel).getByRole('group', { name: legacyQuestion.text })).getByRole('button', {
        name: 'Yes',
      }),
    )
    await user.click(within(panel).getByRole('button', { name: 'Add answers and run again' }))
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({
      ...earlier,
      significant_design_change: `${legacyQuestion.text} Yes.`,
    })
    expect(
      await screen.findByRole('region', { name: "Your answer didn't change the class." }),
    ).toHaveTextContent('Run 3 of 3')
  })

  it.each([
    ['en', 'Add answers and run again', 'Answer 1 question to finish the check'],
    [
      'de',
      'Antworten hinzufügen und erneut prüfen',
      'Beantworten Sie 1 Frage, um die Prüfung abzuschließen',
    ],
  ] as const)(
    'offers one run action for the deciding question and the panel, and sends both (%s)',
    async (language, runAgain, needs) => {
      const bodies = rerunReturns(minimalRisk())
      const result: ClassificationResult = {
        ...annexIIINeedsInfo(),
        follow_up_questions: [
          ...(annexIIINeedsInfo().follow_up_questions ?? []),
          legacyQuestion,
          wordsQuestion,
        ],
      }
      const { user } = await openResult(result, { language })
      const deciding = screen.getByRole('region', { name: ANNEX_III_QUESTION })
      expect(within(deciding).queryByRole('button', { name: /run again|erneut prüfen/ })).toBeNull()
      // One run action on the page, singular or plural, wherever it sits.
      expect(screen.getAllByRole('button', { name: /run again|erneut prüfen/ }).length).toBe(1)
      expect(screen.getByRole('button', { name: runAgain })).toBeVisible()

      await user.click(
        within(deciding).getByRole('button', { name: language === 'en' ? 'No' : 'Nein' }),
      )
      await user.type(screen.getByRole('textbox', { name: wordsQuestion.text }), 'HR reads all.')
      await user.click(screen.getByRole('button', { name: runAgain }))

      await expect.poll(() => bodies.length).toBe(1)
      expect(Object.keys(bodies[0]?.answers ?? {})).toEqual([
        'used_for_recruitment',
        'human_review',
      ])
      // "Needs you" is the inventory's own line for the paused run (one paused check, so one
      // question), not a count of the three questions its screen asked.
      expect(openQuestionCount(result)).toBe(1)
      expect(needs).toBe(i18n.t('inventory.needs.needsInfo', { count: 1 }))
      const lists = await screen.findByRole('region', {
        name:
          language === 'en'
            ? 'What changed in your lists'
            : 'Was sich in Ihren Listen geändert hat',
      })
      expect(within(lists).getAllByRole('definition')[2]?.textContent).toMatch(
        new RegExp(`^${needs}→`),
      )
    },
  )
})

describe('Confirm on an assumed fact', () => {
  const FACT = 'The company bought the tool.'
  const confirmQuestion: FollowUpQuestion = {
    id: 'confirm_the_company_bought_the_tool',
    text: `Please confirm: ${FACT}`,
    options: ['yes', 'no', 'not_sure'],
  }

  function assumesFact(): ClassificationResult {
    return {
      ...decidedHighRisk(),
      deciding_facts: [{ text: FACT, evidence: 'assumed' }],
      follow_up_questions: [confirmQuestion],
    }
  }

  it.each([
    ['en', 'Confirm', /open questions?$/, `You confirmed: “${FACT}”`],
    ['de', 'Bestätigen', /offene Fragen?$/, `Sie haben bestätigt: „${FACT}“`],
  ] as const)(
    'confirms through the engine’s own question, asked only on the card (%s)',
    async (language, confirm, panel, said) => {
      const bodies = rerunReturns(decidedHighRisk())
      const { user } = await openResult(assumesFact(), { language })
      // The fact has one control, Confirm on its card: the panel doesn't ask it again.
      expect(screen.queryByRole('region', { name: panel })).toBeNull()
      expect(screen.queryByRole('group', { name: confirmQuestion.text })).toBeNull()
      const facts = screen.getByRole('complementary', {
        name: language === 'en' ? 'The result rests on' : 'Das Ergebnis beruht auf',
      })
      await user.click(within(facts).getByRole('button', { name: confirm }))

      const banner = await screen.findByRole('region', {
        name:
          language === 'en'
            ? "Your answer didn't change the class."
            : 'Ihre Antwort hat die Einstufung nicht geändert.',
      })
      expect(bodies[0]?.answers).toEqual({
        confirm_the_company_bought_the_tool: `${confirmQuestion.text} ${language === 'en' ? 'Yes' : 'Ja'}.`,
      })
      expect(banner).toHaveTextContent(said)
    },
  )

  it('states a fact no question asks about as the user’s own, in German', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const result: ClassificationResult = {
      ...decidedHighRisk(),
      deciding_facts: [{ text: 'HR reviews every shortlist.', evidence: 'assumed' }],
    }
    const { user } = await openResult(result, { language: 'de' })
    const facts = screen.getByRole('complementary', { name: 'Das Ergebnis beruht auf' })
    await user.click(within(facts).getByRole('button', { name: 'Bestätigen' }))
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({
      confirmed_fact_1: 'Bestätigt: HR reviews every shortlist.',
    })
    expect(
      await screen.findByRole('region', {
        name: 'Ihre Antwort hat die Einstufung nicht geändert.',
      }),
    ).toHaveTextContent('Sie haben bestätigt: „HR reviews every shortlist.“')
  })

  it('sends only the confirmation, not an answer drafted in the panel', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const drafted: FollowUpQuestion = {
      id: 'human_review',
      text: 'Does a person review the shortlist?',
      options: ['yes', 'no', 'not_sure'],
    }
    const result: ClassificationResult = {
      ...assumesFact(),
      follow_up_questions: [confirmQuestion, drafted],
    }
    const { user } = await openResult(result, { run: { answers: { eu_link: 'In the EU. Yes.' } } })
    const panel = screen.getByRole('region', { name: '1 open question' })
    await user.click(within(panel).getByRole('button', { name: 'No' }))
    const facts = screen.getByRole('complementary', { name: 'The result rests on' })
    await user.click(within(facts).getByRole('button', { name: 'Confirm' }))

    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({
      eu_link: 'In the EU. Yes.',
      confirm_the_company_bought_the_tool: `${confirmQuestion.text} Yes.`,
    })
  })
})

describe('The worked example’s questions', () => {
  it('leaves the assumed facts to their cards: no question asks one of them again', async () => {
    await openResult(WORKED_EXAMPLE)
    const facts = screen.getByRole('complementary', { name: 'The result rests on' })
    const assumed = uniqueFacts(WORKED_EXAMPLE.deciding_facts ?? [])
      .filter((fact) => fact.evidence === 'assumed')
      .map((fact) => fact.text)
    expect(within(facts).getAllByRole('button', { name: 'Confirm' })).toHaveLength(4)
    expect(assumed).toHaveLength(4)
    for (const fact of assumed) {
      expect(screen.queryByRole('group', { name: (name) => name.includes(fact) })).toBeNull()
    }
  })
})

describe('The facts step row', () => {
  it('counts the facts the panel beside it shows', async () => {
    // The worked example: 4 facts read, but the result rests on 8 deciding facts, 4 assumed.
    await openResult(WORKED_EXAMPLE)
    const facts = screen.getByRole('complementary', { name: 'The result rests on' })
    const assumedCards = within(facts).getAllByText('Assumed')
    expect(stepRow(/^Facts/)).toHaveTextContent(
      `8 facts found, ${String(assumedCards.length)} assumed`,
    )
    expect(assumedCards).toHaveLength(4)
  })
})

describe('The original-text comparison of a run made by an answer', () => {
  it('checks the same answers under the original text', async () => {
    const bodies = rerunReturns({ ...minimalRisk(), law_version: 'original', obligations: [] })
    const answers = { used_for_recruitment: `${ANNEX_III_QUESTION} No.` }
    await i18n.changeLanguage('en')
    const client = createTestQueryClient()
    putRun(client, {
      toolId: TOOL_ID,
      name: 'Applicant screening',
      description: WORKED_EXAMPLE_DESCRIPTION,
      result: minimalRisk(),
      runNo: 2,
      answers,
    })
    renderRoute(`/app/inventory/${TOOL_ID}?view=reviewer`, client)
    const panel = await screen.findByRole('region', { name: 'Original Act vs amended' })
    await userEvent
      .setup()
      .click(within(panel).getByRole('button', { name: 'Check under the original text' }))
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]).toEqual({
      description: WORKED_EXAMPLE_DESCRIPTION,
      answers,
      language: 'en',
      law_version: 'original',
      as_of: minimalRisk().as_of,
    })
  })
})
