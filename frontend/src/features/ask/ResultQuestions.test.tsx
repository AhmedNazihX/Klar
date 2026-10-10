import { cleanup, screen, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult, QaAnswer, QuestionRequest } from '@/api'
import { putRun, type ClassificationRun } from '@/features/classify/classification-store'
import { WORKED_EXAMPLE, WORKED_EXAMPLE_DESCRIPTION } from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { answered, QA_URL, qaHandlers } from '@/test/qa-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

const TOOL_ID = 'applicant-screening'
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }
/** A whole result screen, its route chunk loaded cold, a question and its answer: more than the
 *  default 5 s in a full run. */
const ROUND_TRIP_MS = 15_000

let sent: QuestionRequest[] = []

/** The result's own first citation, as the API answers a question about it. */
function citingTheResult(result: ClassificationResult): QaAnswer {
  const cited = result.steps.flatMap((step) => step.citations ?? [])[0]
  if (!cited) throw new Error('the fixture result cites nothing')
  return answered({
    answer: 'Yes: the people it screens must be told that the system is used.',
    citations: [cited],
  })
}

async function openResult(
  result: ClassificationResult,
  { view, runNo, language = 'en' }: { view?: 'reviewer'; runNo?: number; language?: 'en' | 'de' },
) {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  const run: ClassificationRun = {
    toolId: TOOL_ID,
    name: 'Applicant screening',
    description: WORKED_EXAMPLE_DESCRIPTION,
    result,
    runNo,
  }
  putRun(client, run)
  const rendered = renderRoute(`/app/inventory/${TOOL_ID}${view ? `?view=${view}` : ''}`, client)
  await screen.findByRole(
    'heading',
    { level: 1, name: 'Applicant screening' },
    { timeout: FIRST_RENDER_MS },
  )
  return rendered
}

/** Puts the question in the field at once (typing it key by key re-renders the whole result
 *  screen each time) and sends it with Enter. */
async function ask(user: UserEvent, field: HTMLElement, question: string): Promise<void> {
  await user.click(field)
  await user.paste(question)
  await user.keyboard('{Enter}')
}

function panel(name = 'Questions about this result'): HTMLElement {
  return screen.getByRole('region', { name })
}

beforeEach(() => {
  sent = []
  window.sessionStorage.clear()
})

describe('Questions about this result', () => {
  it.each([undefined, 'reviewer'] as const)(
    'sends the result with the question and cites its provisions (%s view)',
    async (view) => {
      const user = userEvent.setup()
      server.use(...qaHandlers(sent, () => citingTheResult(WORKED_EXAMPLE)))
      await openResult(WORKED_EXAMPLE, { view })

      const questions = panel()
      await ask(
        user,
        within(questions).getByRole('textbox', { name: 'Ask about this result' }),
        'Do we have to tell applicants that AI was used?',
      )

      expect(await within(questions).findByText(/the people it screens must be told/)).toBeVisible()
      expect(sent).toHaveLength(1)
      expect(sent[0]?.result).toEqual(WORKED_EXAMPLE)
      expect(sent[0]?.law_version).toBe(WORKED_EXAMPLE.law_version)
      expect(sent[0]?.question).toBe('Do we have to tell applicants that AI was used?')
      const chips = within(questions).getByRole('list', { name: 'Provisions cited' })
      expect(within(chips).getAllByRole('button')).toHaveLength(1)
    },
    ROUND_TRIP_MS,
  )

  it('shows the thread beside a result checked under the original text too', async () => {
    server.use(...qaHandlers(sent, () => answered()))
    const original = { ...WORKED_EXAMPLE, law_version: 'original' as const }
    await openResult(original, { view: 'reviewer' })
    expect(panel()).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Original Act vs amended' })).toBeNull()
  })

  it('fills the field from a suggestion without sending it', async () => {
    const user = userEvent.setup()
    server.use(...qaHandlers(sent, () => answered()))
    await openResult(WORKED_EXAMPLE, {})
    const questions = panel()
    await user.click(within(questions).getByRole('button', { name: 'What if we switch vendors?' }))
    expect(within(questions).getByRole('textbox')).toHaveValue('What if we switch vendors?')
    expect(sent).toEqual([])
  })

  it('keeps each run its own thread for the session', async () => {
    const user = userEvent.setup()
    server.use(...qaHandlers(sent, () => answered()))
    await openResult(WORKED_EXAMPLE, { runNo: 1 })
    await ask(user, within(panel()).getByRole('textbox'), 'What counts as a deployer?')
    await within(panel()).findByText(/A deployer is anyone/)

    cleanup()
    await openResult(WORKED_EXAMPLE, { runNo: 1 })
    expect(within(panel()).getByText('What counts as a deployer?')).toBeVisible()

    cleanup()
    await openResult(WORKED_EXAMPLE, { runNo: 2 })
    expect(within(panel()).queryByText('What counts as a deployer?')).toBeNull()
  })

  it('lands an answer still on its way in the thread after switching views', async () => {
    const user = userEvent.setup()
    let release: () => void = () => undefined
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(...qaHandlers(sent, () => answered()))
    server.use(
      http.post(QA_URL, async ({ request }) => {
        sent.push((await request.json()) as QuestionRequest)
        await held
        return HttpResponse.json(citingTheResult(WORKED_EXAMPLE))
      }),
    )
    await openResult(WORKED_EXAMPLE, {})
    await ask(user, within(panel()).getByRole('textbox'), 'Do we have to tell applicants?')
    await within(panel()).findByText('Klar is answering …')

    await user.click(screen.getByRole('button', { name: 'Reviewer' }))
    await screen.findByRole('button', { name: 'Reviewer', pressed: true })
    expect(within(panel()).getByText('Do we have to tell applicants?')).toBeVisible()
    expect(within(panel()).getByText('Klar is answering …')).toBeVisible()

    release()
    expect(await within(panel()).findByText(/the people it screens must be told/)).toBeVisible()
    expect(sent).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'Summary' }))
    expect(await within(panel()).findByText(/the people it screens must be told/)).toBeVisible()
  }, ROUND_TRIP_MS)

  it('moves the focus to the field after a suggestion, so Enter asks it', async () => {
    const user = userEvent.setup()
    server.use(...qaHandlers(sent, () => answered()))
    await openResult(WORKED_EXAMPLE, {})
    const questions = panel()
    await user.click(within(questions).getByRole('button', { name: 'What if we switch vendors?' }))
    expect(within(questions).getByRole('textbox')).toHaveFocus()
    await user.keyboard('{Enter}')
    await within(panel()).findByText(/A deployer is anyone/)
    expect(sent.map((request) => request.question)).toEqual(['What if we switch vendors?'])
  }, ROUND_TRIP_MS)

  it('reads in German', async () => {
    server.use(...qaHandlers(sent, () => answered()))
    await openResult(WORKED_EXAMPLE, { language: 'de' })
    const questions = panel('Fragen zu diesem Ergebnis')
    expect(
      within(questions).getByRole('textbox', { name: 'Frage zu diesem Ergebnis' }),
    ).toBeVisible()
    expect(
      within(questions).getByRole('button', { name: 'Was gilt als menschliche Aufsicht?' }),
    ).toBeVisible()
    expect(
      within(questions).getByText(
        'Die Antworten bleiben bei der KI-Verordnung und den Leitlinien der Kommission. Klar sagt Ihnen nicht, ob Sie die Vorschriften einhalten.',
      ),
    ).toBeVisible()
  })

  it('has no axe violations in the reviewer view with an answer', async () => {
    const user = userEvent.setup()
    server.use(...qaHandlers(sent, () => citingTheResult(WORKED_EXAMPLE)))
    const { container } = await openResult(WORKED_EXAMPLE, { view: 'reviewer' })
    await ask(user, within(panel()).getByRole('textbox'), 'Why?')
    await within(panel()).findByText(/must be told/)
    expect((await axe(container, AXE_OPTIONS)).violations).toEqual([])
  })
})
