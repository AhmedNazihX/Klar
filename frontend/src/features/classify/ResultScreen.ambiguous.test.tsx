// The legally ambiguous result (P22; artboard `ResultAmbiguous`, decision 026 items 3, 4, 11, 12)
// on the recorded ambiguous result: the verdict with the open point, its dates and the legal-review
// line and the Art. 111(2) notice; both readings with their quotes from the corpus (decision 031),
// the applied one marked; what would settle it, with no re-check promise; Draft a request (P28's
// letter); Take it to a lawyer.
import { cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type {
  ClassificationResult,
  ClassifyRequest,
  ClassifyResponse,
  FollowUpQuestion,
  Reading,
  StepName,
  VendorLetterRequest,
} from '@/api'
import type { Language } from '@/i18n'
import { env } from '@/lib/env'
import {
  AMBIGUOUS_PROVISIONS,
  RECORDED_AMBIGUOUS,
  REQUEST_LETTERS,
  requestHandlers,
  SAFETY_QUESTION,
  withLegacy,
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
    showFull: 'Show full text',
    guidance:
      'Final Commission guidelines on high-risk classification (still a draft, 19 May 2026)',
    guidanceOf3March2027:
      'Final Commission guidelines on high-risk classification (still a draft, 3 March 2027)',
    legacy:
      'Art. 111(2): the tool was on the market or in use before 2 August 2028, so the marked high-risk duties apply only if its design or intended purpose changes significantly. The class stays high-risk.',
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
    source: 'Art. 6 Abs. 1, Deutsch',
    showFull: 'Ganzen Text zeigen',
    guidance:
      'Endgültige Leitlinien der Kommission zur Einstufung als Hochrisiko (noch ein Entwurf, 19. Mai 2026)',
    guidanceOf3March2027:
      'Endgültige Leitlinien der Kommission zur Einstufung als Hochrisiko (noch ein Entwurf, 3. März 2027)',
    legacy:
      'Art. 111 Abs. 2: Das Tool war vor dem 2. August 2028 in Verkehr oder in Betrieb, deshalb gelten die markierten Hochrisiko-Pflichten nur, wenn sich seine Konzeption oder Zweckbestimmung erheblich ändert. Die Einstufung bleibt Hochrisiko.',
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
let provisionIds: string[]

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
  provisionIds = []
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
    search = '',
  }: { result?: ClassificationResult; letterStatus?: number; search?: string } = {},
) {
  server.use(...requestHandlers(letterBodies, { letterStatus, provisionIds }))
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  putRun(client, { toolId: TOOL_ID, name: TOOL_NAME, description: DESCRIPTION, result })
  const rendered = renderRoute(`/app/inventory/${TOOL_ID}${search}`, client)
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

/** Art. 6(1), which both readings cite, as the corpus words it in `language`, its line breaks
 *  read as spaces as the screen's text shows them. */
function pointText(language: Language): string {
  const text = AMBIGUOUS_PROVISIONS['art:6:1']?.[language].text
  if (!text) throw new Error(`The fixture has no ${language} text of Art. 6(1).`)
  return text.replace(/\s+/g, ' ')
}

/** The words a shortened quote of Art. 6(1) opens with. */
function pointOpening(language: Language): string {
  return pointText(language).slice(0, 120)
}

/** The text an element shows under one law version: the other version's parts left out. */
function textUnder(element: HTMLElement, law: 'amended' | 'original'): string {
  const copy = element.cloneNode(true) as HTMLElement
  const hidden = law === 'original' ? '.law-amended-only' : '.law-original-only'
  for (const part of copy.querySelectorAll(hidden)) part.remove()
  return copy.textContent
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
    const { user } = await openAmbiguous(language)
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
      expect(card).toHaveTextContent(reading.consequence ?? '')
      // The provision the reading cites, as the corpus words it in the screen's language (the
      // official German text on a German screen): Art. 6(1), shortened, whole on request.
      const quote = await within(card).findByRole('blockquote')
      expect(quote).toHaveAttribute('lang', language)
      expect(quote).toHaveTextContent(pointOpening(language))
      expect(quote).not.toHaveTextContent(pointText(language))
      await user.click(within(card).getByRole('button', { name: copy.showFull }))
      expect(quote).toHaveTextContent(pointText(language))
      expect(within(card).getByText(copy.source)).toBeInTheDocument()
    }
    expect(new Set(provisionIds)).toEqual(new Set(['art:6:1']))
  })

  it('quotes the corpus, never the posted result, even when its quote was changed', async () => {
    const tampered = 'Any AI system that forecasts wear is high-risk.'
    const result = {
      ...RECORDED_AMBIGUOUS,
      steps: RECORDED_AMBIGUOUS.steps.map((step) => {
        const question = step.open_question
        if (!question) return step
        const readings = question.readings.map((reading) => ({
          ...reading,
          citation: reading.citation && { ...reading.citation, quote: tampered },
        })) as typeof question.readings
        return { ...step, open_question: { ...question, readings } }
      }),
    }
    await openAmbiguous(language, { result })
    for (const card of readingCards(language)) {
      expect(await within(card).findByRole('blockquote')).toHaveTextContent(pointOpening(language))
    }
    expect(screen.queryByText(tampered, { exact: false })).toBeNull()
  })

  it('shows the Art. 111(2) notice under the date when the duties carry a marking', async () => {
    await openAmbiguous(language)
    const summary = screen.getByRole('region', { name: copy.result })
    expect(within(summary).queryByRole('note')).toBeNull()
    cleanup()
    await openAmbiguous(language, { result: withLegacy(RECORDED_AMBIGUOUS) })
    const notice = within(screen.getByRole('region', { name: copy.result })).getByRole('note')
    expect(notice).toHaveTextContent(copy.legacy)
  })

  it('dates the applied reading’s consequence as the law switch does, never two dates', async () => {
    const { applied } = recordedReadings()
    const engineWords = applied.consequence ?? ''
    // The recorded result is English: its consequence names the amended route date.
    expect(engineWords).toContain(COPY.en.amendedDate)
    await openAmbiguous(language, { search: '?law=original' })
    const summary = screen.getByRole('region', { name: copy.result })
    const [, card] = readingCards(language)
    expect(textUnder(summary, 'original')).toContain(copy.originalDate)
    expect(textUnder(summary, 'original')).not.toContain(copy.amendedDate)
    expect(textUnder(card, 'original')).toContain(
      engineWords.replace(COPY.en.amendedDate, COPY.en.originalDate),
    )
    expect(textUnder(card, 'original')).not.toContain('2028')
    // Under the amended text the engine's words stand.
    expect(textUnder(card, 'amended')).toContain(engineWords)
    expect(textUnder(card, 'amended')).not.toContain('2027')
  })

  it('keeps a dated consequence without the route’s date as the engine wrote it, under both texts', async () => {
    const consequence = 'If this holds, the high-risk duties apply from 2 August 2029.'
    const result = {
      ...RECORDED_AMBIGUOUS,
      steps: RECORDED_AMBIGUOUS.steps.map((step) => {
        const question = step.open_question
        if (!question) return step
        const readings = question.readings.map((reading) =>
          reading.is_applied ? { ...reading, consequence } : reading,
        ) as typeof question.readings
        return { ...step, open_question: { ...question, readings } }
      }),
    }
    await openAmbiguous(language, { result, search: '?law=original' })
    const [, card] = readingCards(language)
    expect(textUnder(card, 'original')).toContain(consequence)
    expect(textUnder(card, 'amended')).toContain(consequence)
  })

  it('dates the guidance as the engine did, in the screen’s language', async () => {
    const result = withSettledBy(RECORDED_AMBIGUOUS, [
      {
        kind: 'guidance',
        text: 'Final Commission guidelines on high-risk classification (still a draft, 3 March 2027)',
      },
    ])
    await openAmbiguous(language, { result })
    const [, guidance] = settleItems(language) as [HTMLElement, HTMLElement]
    expect(guidance).toHaveTextContent(copy.guidanceOf3March2027)
  })

  it('names guidance off the high-risk check in the engine’s words', async () => {
    const text = 'Commission guidelines on transparency obligations (still a draft, 3 March 2027)'
    const result = variant(withSettledBy(RECORDED_AMBIGUOUS, [{ kind: 'guidance', text }]), {
      step: 'transparency',
    })
    await openAmbiguous(language, { result })
    const [, guidance] = settleItems(language) as [HTMLElement, HTMLElement]
    expect(guidance.textContent).toBe(text)
  })

  it('lists what would settle it, the guidance as a plain item with no re-check promise', async () => {
    await openAmbiguous(language)
    const items = settleItems(language)
    expect(items).toHaveLength(2)
    const [vendor, guidance] = items as [HTMLElement, HTMLElement]
    expect(vendor).toHaveTextContent(copy.vendorReading)
    expect(within(vendor).getByRole('button', { name: copy.draftRequest })).toBeVisible()
    // Named in the screen's language, whatever language the engine wrote it in.
    expect(guidance).toHaveTextContent(copy.guidance)
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
    // The engine's English words: the screen names each kind in its own language.
    const result = withSettledBy(RECORDED_AMBIGUOUS, [
      { kind: 'guidance', text: COPY.en.guidance },
      { kind: 'provider', text: COPY.en.provider },
    ])
    await openAmbiguous(language, { result })
    const items = settleItems(language)
    expect(items.map((item) => item.textContent)).toEqual([
      `${copy.provider}${copy.draftRequest}`,
      copy.guidance,
    ])
  })

  it('asks a provider for no request: it is the vendor', async () => {
    const result = withSettledBy({ ...RECORDED_AMBIGUOUS, role: 'provider' }, [
      { kind: 'provider', text: COPY.en.provider },
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

describe('Questions that don’t bear on the open point', () => {
  /** A role question (Art. 25(1)(b)) and an Art. 111(2) one: neither settles Art. 6(1). */
  const ROLE_QUESTION: FollowUpQuestion = {
    id: 'substantial_modification',
    text: 'Have you changed the forecast tool substantially?',
    about: 'art:25:1:b',
    options: ['yes', 'no', 'not_sure'],
  }
  const LEGACY_QUESTION: FollowUpQuestion = {
    id: 'market_date',
    text: 'When was the tool first put into service?',
    about: 'art:111:2',
    options: [],
  }

  it('keep their own panel, which holds the one run action', async () => {
    const result = {
      ...RECORDED_AMBIGUOUS,
      follow_up_questions: [ROLE_QUESTION, SAFETY_QUESTION, LEGACY_QUESTION],
    }
    await openAmbiguous('en', { result })
    const items = settleItems('en')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent(SAFETY_QUESTION.text)
    const settle = screen.getByRole('region', { name: 'What would settle it' })
    expect(within(settle).queryByText(ROLE_QUESTION.text)).toBeNull()
    expect(within(settle).queryByText(LEGACY_QUESTION.text)).toBeNull()
    expect(within(settle).queryByRole('button', { name: /run again/ })).toBeNull()

    const others = screen.getByRole('region', { name: '2 open questions' })
    expect(within(others).getByText(ROLE_QUESTION.text)).toBeInTheDocument()
    expect(within(others).getByText(LEGACY_QUESTION.text)).toBeInTheDocument()
    expect(within(others).getByRole('button', { name: 'Add answers and run again' })).toBeDisabled()
    expect(screen.getAllByRole('button', { name: /run again/ })).toHaveLength(1)
  })

  it('leave the run action under what would settle it when there are none', async () => {
    const result = { ...RECORDED_AMBIGUOUS, follow_up_questions: [SAFETY_QUESTION] }
    await openAmbiguous('en', { result })
    const settle = screen.getByRole('region', { name: 'What would settle it' })
    expect(
      within(settle).getByRole('button', { name: 'Add answer and run again' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /open question/ })).toBeNull()
  })
})

describe('Export PDF under Take it to a lawyer', () => {
  it('says in place, in the panel, when the report couldn’t be made', async () => {
    server.use(
      http.post(`${env.apiUrl}/reports/result`, () =>
        HttpResponse.json({ detail: 'refused' }, { status: 504 }),
      ),
    )
    const { user } = await openAmbiguous('en')
    const lawyer = screen.getByRole('region', { name: 'Take it to a lawyer' })
    await user.click(within(lawyer).getByRole('button', { name: 'Export PDF' }))
    const alert = await within(lawyer).findByRole('alert')
    expect(alert).not.toHaveClass('absolute')
    expect(alert).not.toHaveClass('top-full')
    // Its wrapper stacks it under the button, in the flow: no anchor for a hanging message.
    expect(alert.parentElement).not.toHaveClass('relative')
    expect(alert.parentElement).toHaveClass('flex-col')
  })
})
