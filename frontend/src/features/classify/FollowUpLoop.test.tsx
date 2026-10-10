// The follow-up loop on a result (P5b; artboards `ResultNeedsInfo`, `ResultRerun`, `Classify`):
// answering re-runs the engine with the answers next to the description, the re-run result shows
// with what it changed, and Undo answer brings the run before back. Without Supabase, as in the
// other result tests: nothing is saved (FollowUpLoop.save.test.tsx covers the saving).
import { screen, within } from '@testing-library/react'
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
import { server } from '@/test/msw-server'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

import { putRun, type ClassificationRun } from './classification-store'

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
  await screen.findByRole(
    'heading',
    { level: 1, name: 'Applicant screening' },
    { timeout: FIRST_RENDER_MS },
  )
  return { user: userEvent.setup(), container }
}

function stepRow(name: RegExp): HTMLElement {
  const section = screen.getByRole('region', {
    name: /How Klar got here|Wie Klar zum Ergebnis kam/,
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
    expect(banner).toHaveTextContent(`You said: “${ANNEX_III_QUESTION} No.”`)
    expect(within(banner).getByText('High-risk, assumed')).toBeInTheDocument()
    expect(within(banner).getByText('Minimal risk')).toBeInTheDocument()
    // The re-run result is the one shown, and the question is gone.
    const summary = screen.getByRole('region', { name: 'Result' })
    expect(within(summary).getByText('Minimal risk')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: ANNEX_III_QUESTION })).toBeNull()
    expect(stepRow(/^3 High-risk/)).toHaveTextContent('Changed: Not high-risk')
    expect(stepRow(/^1 Scope/)).not.toHaveTextContent('Changed')
  })

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
    await user.click(within(question).getByRole('button', { name: 'Add answer and run again' }))

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

  it('a failed re-run keeps the result; Try again sends the same answers once', async () => {
    const bodies: unknown[] = []
    server.use(
      http.post(CLASSIFY_URL, async ({ request }) => {
        bodies.push(await request.json())
        return HttpResponse.json({ detail: 'busy' }, { status: 503 })
      }),
    )
    const { user } = await openResult(annexIIINeedsInfo())
    const question = screen.getByRole('region', { name: ANNEX_III_QUESTION })
    await user.click(within(question).getByRole('button', { name: 'Yes' }))
    await user.click(within(question).getByRole('button', { name: 'Add answer and run again' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("The checks couldn't finish")
    // No class from a failed run: the result shown is still the one before.
    expect(screen.queryByRole('region', { name: /Your answer/ })).toBeNull()
    expect(bodies).toHaveLength(1)

    await user.click(within(alert).getByRole('button', { name: 'Try again' }))
    await expect.poll(() => bodies.length).toBe(2)
    expect(bodies[1]).toEqual(bodies[0])
    expect(bodies[1]).toMatchObject({
      answers: { used_for_recruitment: `${ANNEX_III_QUESTION} Yes.` },
    })
  })

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
    expect(banner).toHaveTextContent(`Sie haben angegeben: „${ANNEX_III_QUESTION} Nein.“`)
    expect(within(banner).getByRole('button', { name: 'Antwort rückgängig machen' })).toBeVisible()
    expect(
      screen.getByRole('region', { name: 'Was sich in Ihren Listen geändert hat' }),
    ).toHaveTextContent('Nichts zu tun')
    expect(stepRow(/^3 Hochrisiko/)).toHaveTextContent('Geändert: ')
  })
})

describe('Please confirm N facts', () => {
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
      'Please confirm 2 facts',
      'Klar assumed these. They can change the result.',
      'No',
      'No.',
    ],
    [
      'de',
      'Bitte bestätigen Sie 2 Angaben',
      'Klar hat diese angenommen. Sie können das Ergebnis ändern.',
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
    const panel = screen.getByRole('region', { name: 'Please confirm 2 facts' })
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
})

describe('Confirm on an assumed fact', () => {
  it('confirms through the engine’s own question and shows the re-run result', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const confirmQuestion: FollowUpQuestion = {
      id: 'confirm_the_company_bought_the_tool',
      text: 'Please confirm: The company bought the tool.',
      options: ['yes', 'no', 'not_sure'],
    }
    const result: ClassificationResult = {
      ...decidedHighRisk(),
      deciding_facts: [{ text: 'The company bought the tool.', evidence: 'assumed' }],
      follow_up_questions: [confirmQuestion],
    }
    const { user } = await openResult(result)
    const facts = screen.getByRole('complementary', { name: 'The result rests on' })
    await user.click(within(facts).getByRole('button', { name: 'Confirm' }))

    await screen.findByRole('region', { name: "Your answer didn't change the class." })
    expect(bodies[0]?.answers).toEqual({
      confirm_the_company_bought_the_tool: 'Please confirm: The company bought the tool. Yes.',
    })
  })

  it('states a fact no question asks about as the user’s own, in German', async () => {
    const bodies = rerunReturns(decidedHighRisk())
    const result: ClassificationResult = {
      ...decidedHighRisk(),
      deciding_facts: [{ text: 'HR reviews every shortlist.', evidence: 'assumed' }],
    }
    await i18n.changeLanguage('de')
    const { user } = await openResult(result, { language: 'de' })
    const facts = screen.getByRole('complementary', { name: 'Das Ergebnis beruht auf' })
    await user.click(within(facts).getByRole('button', { name: 'Bestätigen' }))
    await expect.poll(() => bodies.length).toBe(1)
    expect(bodies[0]?.answers).toEqual({
      confirmed_fact_1: 'Bestätigt: HR reviews every shortlist.',
    })
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
    const panel = await screen.findByRole(
      'region',
      { name: 'Original Act vs amended' },
      { timeout: FIRST_RENDER_MS },
    )
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
