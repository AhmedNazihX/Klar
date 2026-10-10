// The legally ambiguous result (P22; artboard `ResultAmbiguous`, decision 026 items 3, 4, 11, 12)
// on the recorded ambiguous result: the verdict with the open point, its dates and the legal-review
// line; both readings with their citations, the applied one marked; what would settle it, with no
// re-check promise; Draft a request (P28's letter); Take it to a lawyer.
import { cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type {
  ClassificationResult,
  ClassifyRequest,
  ClassifyResponse,
  Reading,
  StepName,
  VendorLetterRequest,
} from '@/api'
import type { Language } from '@/i18n'
import {
  RECORDED_AMBIGUOUS,
  REQUEST_LETTERS,
  requestHandlers,
  SAFETY_QUESTION,
  withSettledBy,
} from '@/test/ambiguous-fixtures'
import { classifyHandler, WORKED_EXAMPLE_EVENTS } from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

import { putRun } from './classification-store'

const TOOL_ID = 'ropeway-wear-forecast'
const TOOL_NAME = 'Ropeway wear forecast'
const DESCRIPTION = 'Forecasts wear on cableway parts.'
// Axe can't compute contrast over glass in jsdom (ResultScreen.test.tsx does the same).
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }
/** The day the artboard was drawn. */
const TODAY = new Date('2026-10-01T09:00:00Z')

const COPY = {
  en: {
    result: 'Result',
    highRisk: 'High-risk',
    assumed: 'Assumed',
    ambiguous: 'Legally ambiguous',
    statement:
      'The facts are clear, but the law doesn’t settle one point. Klar works from the stricter reading.',
    dutiesFrom: 'If high-risk, duties from',
    amendedDate: '2 August 2028',
    originalDate: '2 August 2027',
    monthsAway: 'About 22 months from today',
    legalReview:
      'For a legally ambiguous result, we recommend a legal review before you rely on it.',
    readings: 'The two readings',
    reading: (n: number) => `Reading ${String(n)}`,
    applied: 'Applied until settled',
    notHighRisk: 'Not high-risk',
    source: 'Art. 6(1), English',
    settle: 'What would settle it',
    answer: 'Answer',
    draftRequest: 'Draft a request',
    vendorReading: 'How the vendor reads this point, if they assessed it',
    recheck: /re-?check|when final/i,
    lawyer: 'Take it to a lawyer',
    lawyerBody:
      'The reviewer view sets out both readings, the facts and every quoted provision, ready to export.',
    openReviewer: 'Open reviewer view',
    exportPdf: 'Export PDF',
    draftDocuments: 'Draft documents',
    letter: 'Draft request to the vendor',
    letterIntro:
      'Check the request, fill in the parts marked below, then send it from your own email.',
    copy: 'Copy request',
    letterFailed: 'Klar couldn’t draft the request.',
    copyFailed: 'Klar couldn’t copy the request. Select it and copy it yourself.',
    omnibus: 'The Digital Omnibus changed this text.',
    noBan: 'No match with a banned practice',
    yes: 'Yes',
    runAgain: 'Add answer and run again',
    provider: 'The provider’s own Art. 6(3) assessment, documented under Art. 6(4), if it made one',
  },
  de: {
    result: 'Ergebnis',
    highRisk: 'Hochrisiko',
    assumed: 'Angenommen',
    ambiguous: 'Rechtlich unklar',
    statement:
      'Die Fakten sind klar, aber das Gesetz lässt einen Punkt offen. Klar geht von der strengeren Lesart aus.',
    dutiesFrom: 'Falls Hochrisiko, Pflichten ab',
    amendedDate: '2. August 2028',
    originalDate: '2. August 2027',
    monthsAway: 'In etwa 22 Monaten',
    legalReview:
      'Bei einem rechtlich unklaren Ergebnis empfehlen wir eine rechtliche Prüfung, bevor Sie sich darauf verlassen.',
    readings: 'Die beiden Lesarten',
    reading: (n: number) => `Lesart ${String(n)}`,
    applied: 'Bis zur Klärung angewandt',
    notHighRisk: 'Kein Hochrisiko',
    source: 'Art. 6 Abs. 1, Englisch',
    settle: 'Was den Punkt klären würde',
    answer: 'Beantworten',
    draftRequest: 'Anfrage entwerfen',
    vendorReading: 'Wie der Anbieter diesen Punkt einschätzt, falls er ihn geprüft hat',
    recheck: /erneut|neu prüf|wenn endgültig/i,
    lawyer: 'Rechtlich prüfen lassen',
    lawyerBody:
      'Die Prüfansicht zeigt beide Lesarten, die Fakten und jede zitierte Vorschrift, bereit zum Export.',
    openReviewer: 'Prüfansicht öffnen',
    exportPdf: 'PDF exportieren',
    draftDocuments: 'Dokumente entwerfen',
    letter: 'Entwurf einer Anfrage an den Anbieter',
    letterIntro:
      'Prüfen Sie die Anfrage, ergänzen Sie die markierten Teile und senden Sie sie dann aus Ihrem eigenen E-Mail-Postfach.',
    copy: 'Anfrage kopieren',
    letterFailed: 'Klar konnte die Anfrage nicht entwerfen.',
    copyFailed: 'Klar konnte die Anfrage nicht kopieren. Markieren und kopieren Sie sie selbst.',
    omnibus: 'Der digitale Omnibus hat diesen Text geändert.',
    noBan: 'Kein Treffer bei den verbotenen Praktiken',
    yes: 'Ja',
    runAgain: 'Antwort hinzufügen und erneut prüfen',
    provider:
      'Die eigene Bewertung des Anbieters nach Art. 6 Abs. 3, dokumentiert nach Art. 6 Abs. 4, falls er eine vorgenommen hat',
  },
} as const

let letterBodies: VendorLetterRequest[]

beforeAll(() => {
  // jsdom has no modal dialogs; the browser's open and close are enough here.
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return
    this.open = false
    this.dispatchEvent(new Event('close'))
  }
})

beforeEach(() => {
  // Only the clock is fixed, so MSW and the user events still run on real timers.
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(TODAY)
  letterBodies = []
})

afterEach(() => {
  vi.useRealTimers()
  // The clipboard spies: user-event keeps one clipboard stub across tests.
  vi.restoreAllMocks()
})

async function openAmbiguous(
  language: Language = 'en',
  {
    result = RECORDED_AMBIGUOUS,
    letterStatus,
  }: { result?: ClassificationResult; letterStatus?: number } = {},
) {
  server.use(...requestHandlers(letterBodies, { letterStatus }))
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  putRun(client, { toolId: TOOL_ID, name: TOOL_NAME, description: DESCRIPTION, result })
  const rendered = renderRoute(`/app/inventory/${TOOL_ID}`, client)
  await screen.findByRole('heading', { level: 1, name: TOOL_NAME }, { timeout: FIRST_RENDER_MS })
  return { ...rendered, user: userEvent.setup() }
}

/** The recorded open question's two readings: the stricter, applied one first. */
function recordedReadings(): { applied: Reading; other: Reading } {
  const step = RECORDED_AMBIGUOUS.steps.find((candidate) => candidate.open_question)
  const [applied, other] = step?.open_question?.readings ?? []
  if (!applied || !other) throw new Error('The recorded result has no open question.')
  return { applied, other }
}

function openQuestion(): string {
  const step = RECORDED_AMBIGUOUS.steps.find((candidate) => candidate.open_question)
  if (!step?.open_question) throw new Error('The recorded result has no open question.')
  return step.open_question.question
}

/** `result` with its open question on `step`, its readings' citations marked as the Omnibus
 *  changed them when `isChanged`. */
function variant(
  result: ClassificationResult,
  { step, isChanged = false }: { step?: StepName; isChanged?: boolean },
): ClassificationResult {
  return {
    ...result,
    steps: result.steps.map((candidate) => {
      const question = candidate.open_question
      if (!question) return candidate
      const readings = question.readings.map((reading) => ({
        ...reading,
        citation: reading.citation && { ...reading.citation, changed_by_omnibus: isChanged },
      })) as typeof question.readings
      return {
        ...candidate,
        step: step ?? candidate.step,
        open_question: { ...question, readings },
      }
    }),
  }
}

function readingCards(language: Language): [HTMLElement, HTMLElement] {
  const group = screen.getByRole('group', { name: COPY[language].readings })
  return within(group).getAllByRole('region') as [HTMLElement, HTMLElement]
}

function settleItems(language: Language): HTMLElement[] {
  const settle = screen.getByRole('region', { name: COPY[language].settle })
  return within(within(settle).getByRole('list')).getAllByRole('listitem')
}

describe('The recorded result', () => {
  it('is legally ambiguous on the high-risk check, a deployer, guidance only to settle it', () => {
    const { applied, other } = recordedReadings()
    expect(RECORDED_AMBIGUOUS.status).toBe('legally_ambiguous')
    expect(RECORDED_AMBIGUOUS.role).toBe('deployer')
    expect(applied.is_applied).toBe(true)
    expect(other.risk_class ?? null).toBeNull()
    expect(RECORDED_AMBIGUOUS.follow_up_questions ?? []).toEqual([])
  })
})

describe.each(['en', 'de'] as const)('A legally ambiguous result (%s)', (language) => {
  const copy = COPY[language]

  it('shows the assumed class, the open point, the dates and the legal-review line', async () => {
    await openAmbiguous(language)
    const summary = screen.getByRole('region', { name: copy.result })
    expect(summary).toHaveAttribute('data-risk-class', 'high_risk')
    expect(within(summary).getByText(copy.highRisk)).toBeInTheDocument()
    expect(within(summary).getByText(copy.assumed)).toBeInTheDocument()
    expect(within(summary).getByText(copy.ambiguous)).toBeInTheDocument()
    expect(within(summary).getByText(copy.statement)).toBeInTheDocument()
    expect(within(summary).getByText(openQuestion())).toBeInTheDocument()
    expect(within(summary).getByText(copy.dutiesFrom)).toBeInTheDocument()
    // Both route dates are in the page; the law switch shows one (decision 026 item 11).
    expect(summary).toHaveTextContent(copy.amendedDate)
    expect(summary).toHaveTextContent(copy.originalDate)
    expect(summary).toHaveTextContent(copy.monthsAway)
    expect(within(summary).getByText(copy.legalReview)).toBeInTheDocument()
    // The lilac glass of an ambiguous result, not the high-risk one.
    expect(summary.getAttribute('style')).toContain('rgba(240, 232, 255, 0.5)')
  })

  it('shows both readings with their citations, the applied one marked and last', async () => {
    await openAmbiguous(language)
    const { applied, other } = recordedReadings()
    const group = screen.getByRole('group', { name: copy.readings })
    const cards = within(group).getAllByRole('region')
    expect(
      cards.map((card) => within(card).getByRole('heading', { level: 2 }).textContent),
    ).toEqual([other.title, applied.title])
    const [first, second] = cards as [HTMLElement, HTMLElement]
    expect(within(first).getByText(copy.reading(1))).toBeInTheDocument()
    expect(within(second).getByText(copy.reading(2))).toBeInTheDocument()

    expect(within(second).getByText(copy.applied)).toBeInTheDocument()
    expect(within(first).queryByText(copy.applied)).toBeNull()
    expect(second).toHaveAttribute('data-applied', 'true')
    expect(first).not.toHaveAttribute('data-applied')

    expect(within(second).getByText(copy.highRisk)).toBeInTheDocument()
    expect(within(first).getByText(copy.notHighRisk)).toBeInTheDocument()

    for (const [card, reading] of [
      [first, other],
      [second, applied],
    ] as const) {
      expect(within(card).getByText(reading.explanation)).toBeInTheDocument()
      expect(within(card).getByText(reading.consequence ?? '')).toBeInTheDocument()
      const quote = within(card).getByRole('blockquote')
      expect(quote).toHaveAttribute('lang', 'en')
      // A long quote opens with its first words (Citation); the start is the provision's own.
      expect(quote.textContent).toContain(reading.citation?.quote.slice(0, 60))
      expect(within(card).getByText(copy.source)).toBeInTheDocument()
    }
  })

  it('lists what would settle it, the guidance as a plain item with no re-check promise', async () => {
    await openAmbiguous(language)
    const items = settleItems(language)
    expect(items).toHaveLength(2)
    const [vendor, guidance] = items as [HTMLElement, HTMLElement]
    expect(vendor).toHaveTextContent(copy.vendorReading)
    expect(within(vendor).getByRole('button', { name: copy.draftRequest })).toBeVisible()
    expect(guidance).toHaveTextContent(
      'Final Commission guidelines on high-risk classification (still a draft, 19 May 2026)',
    )
    expect(within(guidance).queryByRole('button')).toBeNull()
    for (const item of items) expect(item.textContent).not.toMatch(copy.recheck)
    // No Answer when the result asks nothing.
    expect(screen.queryByRole('button', { name: copy.answer })).toBeNull()
  })

  it('opens P28’s request letter from Draft a request, naming the tool', async () => {
    const { user } = await openAmbiguous(language)
    await user.click(screen.getByRole('button', { name: copy.draftRequest }))
    const dialog = await screen.findByRole('dialog', { name: copy.letter })
    expect(within(dialog).getByText(copy.letterIntro)).toBeInTheDocument()
    const document = REQUEST_LETTERS[language].document
    expect(document.template).toBe('vendor_request_ambiguous')
    expect(await within(dialog).findByText(document.title)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: copy.copy })).toBeInTheDocument()
    expect(within(dialog).getByText(openQuestion())).toBeInTheDocument()
    expect(letterBodies).toEqual([
      {
        result: JSON.parse(JSON.stringify(RECORDED_AMBIGUOUS)) as unknown,
        language,
        answers: { tool_name: TOOL_NAME },
      },
    ])
  })

  it('says when the request couldn’t be drafted', async () => {
    const { user } = await openAmbiguous(language, { letterStatus: 503 })
    await user.click(screen.getByRole('button', { name: copy.draftRequest }))
    const dialog = await screen.findByRole('dialog', { name: copy.letter })
    expect(await within(dialog).findByText(copy.letterFailed)).toBeInTheDocument()
  })

  it('says when the browser refuses to copy the request', async () => {
    const { user } = await openAmbiguous(language)
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'))
    await user.click(screen.getByRole('button', { name: copy.draftRequest }))
    const dialog = await screen.findByRole('dialog', { name: copy.letter })
    await user.click(await within(dialog).findByRole('button', { name: copy.copy }))
    expect(await within(dialog).findByText(copy.copyFailed)).toBeInTheDocument()
  })

  it('says under a quote the Digital Omnibus changed that it did, and only there', async () => {
    await openAmbiguous(language)
    expect(screen.queryByText(copy.omnibus)).toBeNull()
    cleanup()
    await openAmbiguous(language, { result: variant(RECORDED_AMBIGUOUS, { isChanged: true }) })
    for (const card of readingCards(language)) {
      expect(within(card).getByText(copy.omnibus)).toBeInTheDocument()
    }
  })

  it('names what a classless reading rules out on the Art. 5 check, and nothing on others', async () => {
    await openAmbiguous(language, { result: variant(RECORDED_AMBIGUOUS, { step: 'prohibited' }) })
    const [other, applied] = readingCards(language)
    expect(within(other).getByText(copy.noBan)).toBeInTheDocument()
    expect(within(applied).getByText(copy.highRisk)).toBeInTheDocument()
    cleanup()
    await openAmbiguous(language, {
      result: variant(RECORDED_AMBIGUOUS, { step: 'role_obligations' }),
    })
    const [roleOther] = readingCards(language)
    expect(within(roleOther).queryByText(copy.notHighRisk)).toBeNull()
    expect(within(roleOther).queryByText(copy.noBan)).toBeNull()
    expect(within(roleOther).queryByText(copy.highRisk)).toBeNull()
  })

  it('takes it to a lawyer: the reviewer view and Export PDF, no other export or documents', async () => {
    const { user, router } = await openAmbiguous(language)
    const lawyer = screen.getByRole('region', { name: copy.lawyer })
    expect(within(lawyer).getByText(copy.lawyerBody)).toBeInTheDocument()
    expect(within(lawyer).getByRole('button', { name: copy.exportPdf })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: copy.exportPdf })).toHaveLength(1)
    expect(screen.queryByRole('link', { name: copy.draftDocuments })).toBeNull()
    await user.click(within(lawyer).getByRole('button', { name: copy.openReviewer }))
    await expect.poll(() => router.state.location.search).toEqual({ view: 'reviewer' })
  })

  it('offers a request on the provider’s own assessment when the question names it', async () => {
    const result = withSettledBy(RECORDED_AMBIGUOUS, [
      {
        kind: 'guidance',
        text: 'Final Commission guidelines on high-risk classification (still a draft, 19 May 2026)',
      },
      { kind: 'provider', text: copy.provider },
    ])
    await openAmbiguous(language, { result })
    const items = settleItems(language)
    expect(items.map((item) => item.textContent)).toEqual([
      `${copy.provider}${copy.draftRequest}`,
      'Final Commission guidelines on high-risk classification (still a draft, 19 May 2026)',
    ])
  })

  it('asks a provider for no request: it is the vendor', async () => {
    const result = withSettledBy({ ...RECORDED_AMBIGUOUS, role: 'provider' }, [
      { kind: 'provider', text: copy.provider },
    ])
    await openAmbiguous(language, { result })
    const items = settleItems(language)
    expect(items.map((item) => item.textContent)).toEqual([copy.provider])
    expect(screen.queryByRole('button', { name: copy.draftRequest })).toBeNull()
  })

  it('has no accessibility violations (axe), on the screen and in the request', async () => {
    const { container, user } = await openAmbiguous(language)
    expect((await axe(container, AXE_OPTIONS)).violations).toEqual([])

    await user.click(screen.getByRole('button', { name: copy.draftRequest }))
    const dialog = await screen.findByRole('dialog', { name: copy.letter })
    await within(dialog).findByRole('button', { name: copy.copy })
    expect((await axe(dialog, AXE_OPTIONS)).violations).toEqual([])
  })
})

describe('Answering what would settle it', () => {
  it('opens the question under Answer and runs the checks again with the answer', async () => {
    const bodies: ClassifyRequest[] = []
    const events: ClassifyResponse[] = [
      ...WORKED_EXAMPLE_EVENTS.slice(0, -1),
      { event: 'result', result: RECORDED_AMBIGUOUS },
    ]
    server.use(
      classifyHandler(events, (body) => {
        bodies.push(body as ClassifyRequest)
      }),
    )
    const result = { ...RECORDED_AMBIGUOUS, follow_up_questions: [SAFETY_QUESTION] }
    const { user } = await openAmbiguous('en', { result })

    const [asked] = settleItems('en')
    expect(asked).toHaveTextContent(SAFETY_QUESTION.text)
    const answer = within(asked as HTMLElement).getByRole('button', { name: 'Answer' })
    expect(answer).toHaveAttribute('aria-expanded', 'false')
    expect(within(asked as HTMLElement).queryByRole('button', { name: 'Yes' })).toBeNull()

    await user.click(answer)
    expect(answer).toHaveAttribute('aria-expanded', 'true')
    const choice = within(asked as HTMLElement).getByRole('group', { name: SAFETY_QUESTION.text })
    await user.click(within(choice).getByRole('button', { name: 'Yes' }))
    await user.click(screen.getByRole('button', { name: 'Add answer and run again' }))

    await expect
      .poll(() => bodies)
      .toEqual([
        {
          description: DESCRIPTION,
          language: 'en',
          answers: { inspection_decisions: `${SAFETY_QUESTION.text} Yes.` },
        },
      ])
  })
})
