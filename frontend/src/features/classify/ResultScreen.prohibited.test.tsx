import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult } from '@/api'
import type { Language } from '@/i18n'
import { server } from '@/test/msw-server'
import {
  PROVISIONS,
  prohibitedHandlers,
  RECORDED_PROHIBITED,
  VENDOR_LETTERS,
  type ProhibitedTraffic,
} from '@/test/prohibited-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

import { putRun } from './classification-store'

const TOOL_ID = 'call-mood-scoring'
const TOOL_NAME = 'Call mood scoring'
// Axe can't compute contrast over glass in jsdom (ResultScreen.test.tsx does the same).
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }
/** The day the artboard was drawn: 20 months after the bans began on 2 February 2025. */
const TODAY = new Date('2026-10-01T09:00:00Z')

const COPY = {
  en: {
    now: 'What to do now',
    steps: [
      'Stop using or supplying it in the EU.',
      'Tell the vendor you’ve stopped, and why.',
      'Get legal advice on the data it has already collected and what to do with it.',
    ],
    noRoute:
      'There’s no route to comply: documentation or oversight can’t make a prohibited practice allowed.',
    draft: 'Draft a message',
    statement: 'It matches a practice Art. 5 bans: Art. 5(1)(f). The checks stop at Article 5.',
    since: 'Banned since',
    sinceDate: '2 February 2025',
    sinceAgo: '20 months ago',
    recentAgo: ['Less than a month ago', '1 month ago'],
    legalReview: 'A prohibited practice is serious. We strongly recommend legal advice now.',
    fine: 'Maximum fine',
    amount: '€35 m or 7%',
    fineBody:
      'of a company’s total worldwide annual turnover for the preceding financial year, whichever is higher. For SMEs, including start-ups, whichever is lower.',
    why: 'Why the checks stopped',
    sources: ['Art. 5(1)(f), English', 'Art. 99(3), English', 'Art. 99(6), English'],
    stepsHeading: 'How Klar got here',
    highRisk: '3 High-risk',
    transparency: '4 Transparency',
    notChecked: 'Not checked: a ban ends the checks',
    duties: 'What you need to do',
    letter: 'Draft message to the vendor',
    letterIntro:
      'Check the message, fill in the parts marked below, then send it from your own email.',
    toFillIn: 'To fill in before you send it.',
    close: 'Close',
    letterFailed: 'Klar couldn’t draft the message.',
    tryAgain: 'Try again',
    quoteFailed: [
      'Klar couldn’t load the text of Art. 5(1)(f).',
      'Klar couldn’t load the text of Art. 99(3).',
      'Klar couldn’t load the text of Art. 99(6).',
    ],
  },
  de: {
    now: 'Was jetzt zu tun ist',
    steps: [
      'Verwenden oder liefern Sie es in der EU nicht mehr.',
      'Sagen Sie dem Anbieter, dass Sie es nicht mehr verwenden, und warum.',
      'Holen Sie rechtlichen Rat ein, was mit den bereits erhobenen Daten geschehen soll.',
    ],
    noRoute:
      'Es gibt keinen Weg zur Konformität: Dokumentation oder Aufsicht machen eine verbotene Praktik nicht zulässig.',
    draft: 'Nachricht entwerfen',
    statement:
      'Es entspricht einer Praktik, die Art. 5 verbietet: Art. 5 Abs. 1 Buchst. f. Die Prüfung endet bei Artikel 5.',
    since: 'Verboten seit',
    sinceDate: '2. Februar 2025',
    sinceAgo: 'vor 20 Monaten',
    recentAgo: ['vor weniger als einem Monat', 'vor 1 Monat'],
    legalReview:
      'Eine verbotene Praktik ist ernst. Wir empfehlen dringend, jetzt rechtlichen Rat einzuholen.',
    fine: 'Höchstbußgeld',
    amount: '35 Mio. € oder 7 %',
    fineBody:
      'des gesamten weltweiten Jahresumsatzes eines Unternehmens im vorangegangenen Geschäftsjahr, je nachdem, welcher Betrag höher ist. Für KMU, einschließlich Start-ups, gilt der niedrigere Betrag.',
    why: 'Warum die Prüfung endete',
    sources: [
      'Art. 5 Abs. 1 Buchst. f, Deutsch',
      'Art. 99 Abs. 3, Deutsch',
      'Art. 99 Abs. 6, Deutsch',
    ],
    stepsHeading: 'Wie Klar zum Ergebnis kam',
    highRisk: '3 Hochrisiko',
    transparency: '4 Transparenz',
    notChecked: 'Nicht geprüft: Ein Verbot beendet die Prüfung',
    duties: 'Was Sie tun müssen',
    letter: 'Entwurf einer Nachricht an den Anbieter',
    letterIntro:
      'Prüfen Sie die Nachricht, ergänzen Sie die markierten Teile und senden Sie sie dann aus Ihrem eigenen E-Mail-Postfach.',
    toFillIn: 'Vor dem Senden auszufüllen.',
    close: 'Schließen',
    letterFailed: 'Klar konnte die Nachricht nicht entwerfen.',
    tryAgain: 'Erneut versuchen',
    quoteFailed: [
      'Klar konnte den Text von Art. 5 Abs. 1 Buchst. f nicht laden.',
      'Klar konnte den Text von Art. 99 Abs. 3 nicht laden.',
      'Klar konnte den Text von Art. 99 Abs. 6 nicht laden.',
    ],
  },
} as const

let traffic: ProhibitedTraffic

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
  traffic = { lookups: [], letterBodies: [] }
})

afterEach(() => {
  vi.useRealTimers()
})

async function openProhibited(
  language: Language = 'en',
  {
    result = RECORDED_PROHIBITED,
    ...failures
  }: { result?: ClassificationResult; letterStatus?: number; provisionStatus?: number } = {},
) {
  server.use(...prohibitedHandlers(traffic, failures))
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  putRun(client, { toolId: TOOL_ID, name: TOOL_NAME, description: 'Mood scores.', result })
  const rendered = renderRoute(`/app/inventory/${TOOL_ID}`, client)
  await screen.findByRole('heading', { level: 1, name: TOOL_NAME }, { timeout: FIRST_RENDER_MS })
  return rendered
}

/** A provision's text as the corpus words it, from the fixture. */
function textOf(provisionId: string, language: Language): string {
  const text = PROVISIONS[provisionId]?.[language].text
  if (!text) throw new Error(`The fixture has no ${language} text of ${provisionId}.`)
  return text
}

function stepRow(name: string): HTMLElement {
  const steps = screen.getByRole('region', { name: COPY[i18n.language as Language].stepsHeading })
  return within(steps).getByRole('button', { name: new RegExp(`^${name}`) })
}

describe.each(['en', 'de'] as const)('A recorded prohibited result (%s)', (language) => {
  const copy = COPY[language]

  it('shows the three steps, the Art. 5 quote, the fine tile and no duty checklist', async () => {
    await openProhibited(language)

    const now = screen.getByRole('region', { name: copy.now })
    expect(within(now).getByText(copy.noRoute)).toBeInTheDocument()
    const steps = within(within(now).getByRole('list')).getAllByRole('listitem')
    expect(steps.map((step) => step.textContent)).toEqual([
      `1${copy.steps[0]}`,
      `2${copy.steps[1]}${copy.draft}`,
      `3${copy.steps[2]}`,
    ])
    expect(within(steps[1] as HTMLElement).getByRole('button', { name: copy.draft })).toBeVisible()

    // The deciding point, word for word from the corpus in the screen's language.
    const why = screen.getByRole('region', { name: copy.why })
    expect(await within(why).findByText(copy.sources[0])).toBeInTheDocument()
    expect(within(why).getByRole('blockquote')).toHaveTextContent(textOf('art:5:1:f', language))

    const fine = screen.getByRole('region', { name: copy.fine })
    expect(within(fine).getByText(copy.amount)).toBeInTheDocument()
    expect(within(fine).getByText(copy.fineBody)).toBeInTheDocument()
    expect(await within(fine).findByText(copy.sources[1])).toBeInTheDocument()
    expect(await within(fine).findByText(copy.sources[2])).toBeInTheDocument()
    const quotes = within(fine).getAllByRole('blockquote')
    expect(quotes.map((quote) => quote.textContent)).toEqual(
      [textOf('art:99:3', language), textOf('art:99:6', language)].map((text) =>
        language === 'en' ? `“${text}”` : `„${text}“`,
      ),
    )
    for (const quote of [...quotes, within(why).getByRole('blockquote')]) {
      expect(quote).toHaveAttribute('lang', language)
    }

    expect(stepRow(copy.highRisk)).toHaveTextContent(copy.notChecked)
    expect(stepRow(copy.transparency)).toHaveTextContent(copy.notChecked)
    expect(screen.queryByRole('region', { name: copy.duties })).not.toBeInTheDocument()
  })

  it('shows the class, where the checks stopped, the date banned since and the legal advice line', async () => {
    await openProhibited(language)
    const summary = screen.getByRole('region', { name: language === 'en' ? 'Result' : 'Ergebnis' })
    expect(within(summary).getByText(copy.statement)).toBeInTheDocument()
    expect(within(summary).getByText(copy.since)).toBeInTheDocument()
    expect(within(summary).getByText(copy.sinceDate)).toBeInTheDocument()
    expect(within(summary).getByText(copy.sinceAgo)).toBeInTheDocument()
    expect(within(summary).getByText(copy.legalReview)).toBeInTheDocument()
  })

  it('reads every quote from the corpus at the result’s law version, date and the screen’s language', async () => {
    await openProhibited(language)
    await screen.findAllByText(copy.sources[2])
    expect([...traffic.lookups].sort((a, b) => a.provisionId.localeCompare(b.provisionId))).toEqual(
      ['art:5:1:f', 'art:99:3', 'art:99:6'].map((provisionId) => ({
        provisionId,
        language,
        lawVersion: 'amended',
        asOf: '2026-09-30',
      })),
    )
  })

  it('opens the drafted message to the vendor', async () => {
    const user = userEvent.setup()
    await openProhibited(language)
    await user.click(screen.getByRole('button', { name: copy.draft }))

    const dialog = await screen.findByRole('dialog', { name: copy.letter })
    const letter = VENDOR_LETTERS[language].document
    expect(
      await within(dialog).findByRole('heading', { level: 1, name: letter.title }),
    ).toBeInTheDocument()
    expect(within(dialog).getByText(language === 'en' ? 'DRAFT' : 'ENTWURF')).toBeInTheDocument()
    // The finding quotes Art. 5(1)(f) from the corpus, in the letter's language.
    const findingSection = letter.sections.find((section) => section.key === 'finding')
    const finding = within(dialog).getByRole('region', { name: findingSection?.heading })
    const [quote] = findingSection?.quotes ?? []
    expect(quote?.language).toBe(language)
    expect(within(finding).getByRole('blockquote')).toHaveTextContent(quote?.quote ?? '')
    expect(within(dialog).getByText(copy.letterIntro)).toBeInTheDocument()
    expect(within(dialog).getAllByText(copy.toFillIn)).toHaveLength(3)
    expect(within(dialog).getByText(letter.disclaimer, { exact: false })).toBeInTheDocument()

    expect(traffic.letterBodies).toEqual([{ result: RECORDED_PROHIBITED, language, answers: {} }])

    await user.click(within(dialog).getByRole('button', { name: copy.close }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: copy.draft })).toBeInTheDocument()
  })

  it.each([
    ['2025-02-10', 0],
    ['2025-03-04', 1],
  ] as const)('counts the time since the ban began on %s', async (today, index) => {
    vi.setSystemTime(new Date(`${today}T09:00:00Z`))
    await openProhibited(language)
    const summary = screen.getByRole('region', { name: language === 'en' ? 'Result' : 'Ergebnis' })
    expect(within(summary).getByText(copy.recentAgo[index])).toBeInTheDocument()
  })

  it('says when a provision’s text can’t be loaded', async () => {
    await openProhibited(language, { provisionStatus: 503 })
    expect(await screen.findByText(copy.quoteFailed[1])).toBeInTheDocument()
    expect(screen.getByText(copy.quoteFailed[0])).toBeInTheDocument()
    expect(screen.getByText(copy.quoteFailed[2])).toBeInTheDocument()
  })

  it('offers to try a failed message again, sending one request per try', async () => {
    const user = userEvent.setup()
    await openProhibited(language, { letterStatus: 503 })
    await user.click(screen.getByRole('button', { name: copy.draft }))
    const dialog = await screen.findByRole('dialog', { name: copy.letter })
    expect(await within(dialog).findByText(copy.letterFailed)).toBeInTheDocument()
    expect(traffic.letterBodies).toHaveLength(1)

    server.use(...prohibitedHandlers(traffic))
    await user.click(within(dialog).getByRole('button', { name: copy.tryAgain }))
    expect(
      await within(dialog).findByRole('heading', { name: VENDOR_LETTERS[language].document.title }),
    ).toBeInTheDocument()
    expect(traffic.letterBodies).toHaveLength(2)
  })
})

describe('The prohibited layout', () => {
  it('has no accessibility violations, with the message open too', async () => {
    const user = userEvent.setup()
    const { container } = await openProhibited()
    await screen.findByText('Art. 99(6), English')
    expect((await axe(container, AXE_OPTIONS)).violations).toEqual([])

    await user.click(screen.getByRole('button', { name: 'Draft a message' }))
    const dialog = await screen.findByRole('dialog', { name: 'Draft message to the vendor' })
    await within(dialog).findByRole('heading', { level: 1 })
    expect((await axe(dialog, AXE_OPTIONS)).violations).toEqual([])
  })

  it('keeps the summary that asks its question for a ban that is only assumed', async () => {
    await openProhibited('en', {
      result: { ...RECORDED_PROHIBITED, status: 'needs_more_information' },
    })
    expect(screen.queryByRole('region', { name: 'What to do now' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Draft a message' })).not.toBeInTheDocument()
    expect(traffic.lookups).toEqual([])
  })
})
