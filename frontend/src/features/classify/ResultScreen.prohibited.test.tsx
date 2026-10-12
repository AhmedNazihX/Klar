import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type { Citation, ClassificationResult } from '@/api'
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
      'Ask the vendor to confirm the finding and stop supplying it to you.',
      'Get legal advice on the data it has already collected and what to do with it.',
    ],
    noRoute:
      'There’s no route to comply: documentation or oversight can’t make a prohibited practice allowed.',
    draft: 'Draft a message',
    statement:
      'It matches a practice Art. 5 bans: recognising emotions in the workplace or in education (Art. 5(1)(f)). The checks stop at Article 5.',
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
    dutiesRow: 'Duties',
    draftLabel: 'DRAFT',
    notChecked: 'Not checked: a ban ends the checks',
    duties: 'What you need to do',
    draftDocuments: 'Draft documents',
    exportPdf: 'Export PDF',
    copy: 'Copy message',
    copied: 'Copied. Paste it into your email.',
    copyFailed: 'Klar couldn’t copy the message. Select it and copy it yourself.',
    copiedQuote: (quote: string) => `“${quote}” (Art. 5(1)(f), English)`,
    preparedWith: 'Draft prepared with Klar.',
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
      'Bitten Sie den Anbieter, das Ergebnis zu bestätigen und es Ihnen nicht weiter bereitzustellen.',
      'Holen Sie rechtlichen Rat ein, was mit den bereits erhobenen Daten geschehen soll.',
    ],
    noRoute:
      'Es gibt keinen Weg zur Konformität: Dokumentation oder Aufsicht machen eine verbotene Praktik nicht zulässig.',
    draft: 'Nachricht entwerfen',
    statement:
      'Es entspricht einer Praktik, die Art. 5 verbietet: Emotionserkennung am Arbeitsplatz oder in Bildungseinrichtungen (Art. 5 Abs. 1 Buchst. f). Die Prüfung endet bei Artikel 5.',
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
    dutiesRow: 'Pflichten',
    draftLabel: 'ENTWURF',
    notChecked: 'Nicht geprüft: Ein Verbot beendet die Prüfung',
    duties: 'Was Sie tun müssen',
    draftDocuments: 'Dokumente entwerfen',
    exportPdf: 'PDF exportieren',
    copy: 'Nachricht kopieren',
    copied: 'Kopiert. Fügen Sie sie in Ihre E-Mail ein.',
    copyFailed: 'Klar konnte die Nachricht nicht kopieren. Markieren und kopieren Sie sie selbst.',
    copiedQuote: (quote: string) => `„${quote}“ (Art. 5 Abs. 1 Buchst. f, Deutsch)`,
    preparedWith: 'Entwurf erstellt mit Klar.',
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
  // The clipboard spies: user-event keeps one clipboard stub across tests.
  vi.restoreAllMocks()
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
  await screen.findByRole('heading', { level: 1, name: TOOL_NAME })
  return rendered
}

/** A provision's text as the corpus words it, from the fixture. */
function textOf(provisionId: string, language: Language): string {
  const text = PROVISIONS[provisionId]?.[language].text
  if (!text) throw new Error(`The fixture has no ${language} text of ${provisionId}.`)
  return text
}

function summaryRegion(): HTMLElement {
  return screen.getByRole('region', { name: i18n.language === 'de' ? 'Ergebnis' : 'Result' })
}

/** `result` with `ids` cited on its Art. 5 step after the ones it has. */
function withBanCitations(result: ClassificationResult, ids: string[]): ClassificationResult {
  return {
    ...result,
    steps: result.steps.map((step) => {
      if (step.step !== 'prohibited') return step
      const citations: Citation[] = step.citations ?? []
      const [first] = citations
      if (!first) throw new Error('The recorded Art. 5 step cites nothing.')
      const added = ids.map((provisionId): Citation => ({ ...first, provision_id: provisionId }))
      return { ...step, citations: [...citations, ...added] }
    }),
  }
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
    expect(stepRow(copy.dutiesRow)).toHaveTextContent(copy.notChecked)
    expect(screen.queryByRole('region', { name: copy.duties })).not.toBeInTheDocument()
  })

  it('offers no documents to draft, only the PDF export', async () => {
    await openProhibited(language)
    expect(screen.queryByRole('link', { name: copy.draftDocuments })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: copy.exportPdf })).toBeInTheDocument()
  })

  it('copies the message as plain text, naming the tool, for the user’s own email', async () => {
    const user = userEvent.setup()
    await openProhibited(language)
    // userEvent.setup() puts a clipboard stub on the navigator; watch what reaches it.
    const writeText = vi.spyOn(navigator.clipboard, 'writeText')
    await user.click(screen.getByRole('button', { name: copy.draft }))
    const dialog = await screen.findByRole('dialog', { name: copy.letter })
    await user.click(await within(dialog).findByRole('button', { name: copy.copy }))

    expect(writeText).toHaveBeenCalledTimes(1)
    const document = VENDOR_LETTERS[language].document
    const finding = document.sections.find((section) => section.key === 'finding')
    const quote = finding?.quotes?.[0]?.quote ?? ''
    const text = writeText.mock.calls[0]?.[0] ?? ''
    const blocks = text.split('\n\n')
    expect(blocks[0]).toBe(`${document.title} (${copy.draftLabel})`)
    expect(blocks).toContain(`${document.sections[0]?.heading ?? ''}\n[${copy.toFillIn}]`)
    expect(blocks).toContain(`${document.sections[1]?.heading ?? ''}\n${TOOL_NAME}`)
    expect(blocks).toContain(
      [finding?.heading, ...(finding?.paragraphs ?? []), copy.copiedQuote(quote)].join('\n'),
    )
    expect(text.match(new RegExp(`\\[${copy.toFillIn}\\]`, 'g'))).toHaveLength(2)
    expect(blocks.at(-1)).toBe(`${copy.preparedWith} ${document.disclaimer}`)
    expect(await within(dialog).findByText(copy.copied)).toBeInTheDocument()
  })

  it('says when the browser refuses the clipboard', async () => {
    const user = userEvent.setup()
    await openProhibited(language)
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'))
    await user.click(screen.getByRole('button', { name: copy.draft }))
    const dialog = await screen.findByRole('dialog', { name: copy.letter })
    await user.click(await within(dialog).findByRole('button', { name: copy.copy }))
    expect(await within(dialog).findByText(copy.copyFailed)).toBeInTheDocument()
    expect(within(dialog).queryByText(copy.copied)).not.toBeInTheDocument()
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
    // The tool's name comes from the inventory; the recipient and the sender stay to fill in.
    const tool = letter.sections.find((section) => section.key === 'tool')
    expect(within(dialog).getByRole('region', { name: tool?.heading })).toHaveTextContent(TOOL_NAME)
    expect(within(dialog).getAllByText(copy.toFillIn)).toHaveLength(2)
    expect(within(dialog).getByText(letter.disclaimer, { exact: false })).toBeInTheDocument()

    expect(traffic.letterBodies).toEqual([
      { result: RECORDED_PROHIBITED, language, answers: { tool_name: TOOL_NAME } },
    ])

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
    // Its class isn't settled: plain glass, not the ban's red tint, and its documents stay open.
    expect(summaryRegion()).not.toHaveAttribute('style')
    expect(screen.getByRole('link', { name: 'Draft documents' })).toBeInTheDocument()
  })

  it('tints a decided ban’s summary red', async () => {
    await openProhibited()
    expect(summaryRegion().getAttribute('style')).toContain('rgba(255, 226, 226, 0.5)')
  })

  it.each([
    [
      'en',
      'It matches a practice Art. 5 bans: recognising emotions in the workplace or in education (Art. 5(1)(f)) and biometric categorisation to infer sensitive traits such as race, political opinions or sexual orientation (Art. 5(1)(g)). The checks stop at Article 5.',
    ],
    [
      'de',
      'Es entspricht einer Praktik, die Art. 5 verbietet: Emotionserkennung am Arbeitsplatz oder in Bildungseinrichtungen (Art. 5 Abs. 1 Buchst. f) und biometrische Kategorisierung, um sensible Merkmale wie ethnische Herkunft, politische Meinungen oder sexuelle Orientierung abzuleiten (Art. 5 Abs. 1 Buchst. g). Die Prüfung endet bei Artikel 5.',
    ],
  ] as const)('names each ban point in plain words (%s)', async (language, statement) => {
    const result = withBanCitations(RECORDED_PROHIBITED, ['art:5:1:g'])
    await openProhibited(language, { result })
    expect(within(summaryRegion()).getByText(statement)).toBeInTheDocument()
  })

  it('leaves out a cited point that applies only later (Art. 5(1)(ba) before 2 December 2026)', async () => {
    const result = withBanCitations(RECORDED_PROHIBITED, ['art:5:1:ba'])
    await openProhibited('en', { result })
    const why = screen.getByRole('region', { name: 'Why the checks stopped' })
    expect(await within(why).findByText('Art. 5(1)(f), English')).toBeInTheDocument()
    expect(within(why).getAllByRole('blockquote')).toHaveLength(1)
    expect(within(why).queryByText(/5\(1\)\(ba\)/)).not.toBeInTheDocument()
    expect(within(summaryRegion()).getByText(COPY.en.statement)).toBeInTheDocument()
    expect(within(summaryRegion()).getByText(COPY.en.sinceDate)).toBeInTheDocument()
    await screen.findAllByText('Art. 99(6), English')
    expect(traffic.lookups.map((lookup) => lookup.provisionId)).not.toContain('art:5:1:ba')
  })
})
