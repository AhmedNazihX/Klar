import { cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import type { QaAnswer, QuestionRequest } from '@/api'
import { env } from '@/lib/env'
import { server } from '@/test/msw-server'
import { answered, outsideCorpus, QA_URL, qaHandlers } from '@/test/qa-fixtures'
import { renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

// Axe can't compute contrast over glass in jsdom (AppFrame.test.tsx does the same).
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }
const PROVISION_URL = `${env.apiUrl}/provisions/:provisionId`

let sent: QuestionRequest[] = []

function serve(reply: () => QaAnswer | number): void {
  server.use(...qaHandlers(sent, reply))
}

async function openAsk(path = '/app/ask', language: 'en' | 'de' = 'en'): Promise<void> {
  await i18n.changeLanguage(language)
  renderRoute(path)
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
}

function field(name = 'Your question'): HTMLElement {
  return screen.getByRole('textbox', { name })
}

beforeEach(() => {
  sent = []
  window.sessionStorage.clear()
})

describe('Ask about the Act', () => {
  it('answers a question with the provisions it rests on, sending it once', async () => {
    const user = userEvent.setup()
    serve(() => answered())
    await openAsk()

    await user.type(field(), '  What counts as a deployer?  {Enter}')

    expect(await screen.findByText(/A deployer is anyone who uses an AI system/)).toBeVisible()
    expect(sent).toEqual([
      {
        question: 'What counts as a deployer?',
        language: 'en',
        law_version: 'amended',
        result: null,
      },
    ])
    const chips = screen.getByRole('list', { name: 'Provisions cited' })
    expect(
      within(chips)
        .getAllByRole('button')
        .map((chip) => chip.textContent),
    ).toEqual(['Art. 3(4)', 'Guidelines on the AI system definition, para. 12'])
    expect(field()).toHaveValue('')
    expect(screen.queryByText(/No provisions cited/)).toBeNull()
  })

  it('keeps Shift+Enter as a new line and never sends an empty question', async () => {
    const user = userEvent.setup()
    serve(() => answered())
    await openAsk()
    const send = screen.getByRole('button', { name: 'Ask' })
    expect(send).toHaveAttribute('aria-disabled', 'true')

    await user.click(send)
    await user.type(field(), '   {Enter}')
    await user.type(field(), 'First line{Shift>}{Enter}{/Shift}second line')

    expect(field()).toHaveValue('   First line\nsecond line')
    expect(send).toHaveAttribute('aria-disabled', 'false')
    expect(sent).toEqual([])
  })

  it('shows a question outside the AI Act with no provision cited', async () => {
    const user = userEvent.setup()
    serve(() => outsideCorpus())
    await openAsk()

    await user.type(field(), 'Are we GDPR compliant?{Enter}')

    expect(
      await screen.findByText('No provisions cited: the question is outside the AI Act.'),
    ).toBeVisible()
    expect(screen.getByText(/That's outside what I can answer/)).toBeVisible()
    expect(screen.queryByRole('list', { name: 'Provisions cited' })).toBeNull()
  })

  it('opens a cited article from the corpus and guidance as the answer quotes it', async () => {
    const user = userEvent.setup()
    const lookups: string[] = []
    serve(() => answered())
    server.use(
      http.get(PROVISION_URL, ({ request, params }) => {
        const query = new URL(request.url).searchParams
        lookups.push(
          `${String(params.provisionId)} ${String(query.get('language'))} ${String(query.get('law_version'))} ${String(query.get('as_of'))}`,
        )
        return HttpResponse.json({
          provision_id: 'art:3:4',
          doc_key: 'ai-act-consolidated',
          document_title: 'AI Act',
          doc_type: 'law',
          law_version: 'amended',
          status: 'consolidated',
          language: 'en',
          english_only: false,
          heading: null,
          text: "'deployer' means the corpus's own words",
          valid_from: '2024-08-01',
          valid_to: null,
          as_of: '2026-10-10',
          disclaimer: 'x',
        })
      }),
    )
    await openAsk()
    await user.type(field(), 'What counts as a deployer?{Enter}')

    await user.click(await screen.findByRole('button', { name: 'Art. 3(4)' }))
    expect(await screen.findByText(/the corpus's own words/)).toBeVisible()
    expect(lookups).toEqual(['art:3:4 en amended 2026-10-10'])

    const guidance = screen.getByRole('button', {
      name: 'Guidelines on the AI system definition, para. 12',
    })
    await user.click(guidance)
    expect(guidance).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(/who uses a system under its own authority/)).toBeVisible()
    expect(screen.getByText(/, English, draft$/)).toBeVisible()
  })

  it('fills the field from "Try asking" without sending anything', async () => {
    const user = userEvent.setup()
    serve(() => answered())
    await openAsk()

    await user.click(
      screen.getByRole('button', { name: 'Do the Article 50 duties apply to internal tools?' }),
    )

    expect(field()).toHaveValue('Do the Article 50 duties apply to internal tools?')
    expect(sent).toEqual([])
  })

  it('shows a failure, and Try again sends the question once more on the click alone', async () => {
    const user = userEvent.setup()
    const replies: (QaAnswer | number)[] = [503, answered()]
    serve(() => replies.shift() ?? 500)
    await openAsk()

    await user.type(field(), 'What counts as a deployer?{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Klar couldn’t answer this question. Please try again.',
    )
    expect(sent).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText(/A deployer is anyone/)).toBeVisible()
    expect(sent).toHaveLength(2)
    expect(sent[1]?.question).toBe('What counts as a deployer?')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('says when there were too many questions', async () => {
    const user = userEvent.setup()
    serve(() => 429)
    await openAsk()
    await user.type(field(), 'What counts as a deployer?{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Too many questions in a short time. Please wait a minute, then try again.',
    )
  })

  it('asks under the original text when the switch says so', async () => {
    const user = userEvent.setup()
    serve(() => answered({ law_version: 'original', as_of: null }))
    await openAsk('/app/ask?law=original')

    expect(
      screen.getByText(
        'Answers use the original AI Act of 2024. Klar won’t tell you whether you’re compliant.',
      ),
    ).toBeVisible()
    await user.type(field(), 'What counts as a deployer?{Enter}')
    await screen.findByText(/A deployer is anyone/)
    expect(sent[0]?.law_version).toBe('original')
  })

  it('lists the texts the answers draw on, the draft marked', async () => {
    serve(() => answered())
    await openAsk()
    const panel = screen.getByRole('region', { name: 'Answers draw on' })
    expect(await within(panel).findByText('AI Act, consolidated 27 Jul 2026')).toBeVisible()
    const items = within(panel)
      .getAllByRole('listitem')
      .map((item) => item.textContent)
    expect(items).toEqual([
      'AI Act, consolidated 27 Jul 2026Consolidation',
      'Regulation (EU) 2026/1744Law',
      'Guidelines on high-risk classificationDraft',
    ])
  })

  it('keeps the answered questions for the session, and only those', async () => {
    const user = userEvent.setup()
    const replies: (QaAnswer | number)[] = [answered(), 503]
    serve(() => replies.shift() ?? 500)
    await openAsk()
    await user.type(field(), 'What counts as a deployer?{Enter}')
    await screen.findByText(/A deployer is anyone/)
    await user.type(field(), 'And a provider?{Enter}')
    await screen.findByRole('alert')

    cleanup()
    await openAsk()

    expect(screen.getByText('What counts as a deployer?')).toBeVisible()
    expect(screen.getByText(/A deployer is anyone/)).toBeVisible()
    expect(screen.queryByText('And a provider?')).toBeNull()
    expect(window.localStorage.getItem('klar.qa.ask')).toBeNull()
    expect(sent).toHaveLength(2)
  })

  it('reads in German, and sends the question in German', async () => {
    const user = userEvent.setup()
    serve(() => outsideCorpus())
    await openAsk('/app/ask', 'de')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Fragen zur KI-Verordnung')
    expect(
      screen.getByText(
        'Klare Antworten, jeweils mit den Vorschriften, auf denen sie beruhen. Auf Deutsch oder Englisch.',
      ),
    ).toBeVisible()
    expect(
      screen.getByText(
        'Die Antworten beruhen auf der KI-Verordnung in der Fassung vom 27. Juli 2026. Klar sagt Ihnen nicht, ob Sie die Vorschriften einhalten.',
      ),
    ).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Fragen Sie zum Beispiel' })).toBeVisible()
    await user.type(field('Ihre Frage'), 'Sind wir konform?{Enter}')
    expect(
      await screen.findByText(
        'Keine Vorschriften zitiert: Die Frage liegt außerhalb der KI-Verordnung.',
      ),
    ).toBeVisible()
    expect(sent[0]?.language).toBe('de')
  })

  it('moves the focus to the field after "Try asking", so Enter asks the question', async () => {
    const user = userEvent.setup()
    serve(() => answered())
    await openAsk()

    await user.click(screen.getByRole('button', { name: 'What changed with the Digital Omnibus?' }))
    expect(field()).toHaveFocus()
    await user.keyboard('{Enter}')

    await screen.findByText(/A deployer is anyone/)
    expect(sent.map((request) => request.question)).toEqual([
      'What changed with the Digital Omnibus?',
    ])
  })

  it('sends nothing more while an answer is on its way', async () => {
    const user = userEvent.setup()
    let release: () => void = () => undefined
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    serve(() => answered())
    server.use(
      http.post(QA_URL, async ({ request }) => {
        sent.push((await request.json()) as QuestionRequest)
        await held
        return HttpResponse.json(answered())
      }),
    )
    await openAsk()

    await user.type(field(), 'What counts as a deployer?{Enter}')
    await screen.findByText('Klar is answering …')
    await user.type(field(), 'And a provider?{Enter}')
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    expect(sent).toHaveLength(1)

    release()
    await screen.findByText(/A deployer is anyone/)
    expect(sent).toHaveLength(1)
    expect(field()).toHaveValue('And a provider?')
  })

  it.each([
    ['en', 'No provisions cited: the question is outside the AI Act.'],
    ['de', 'Keine Vorschriften zitiert: Die Frage liegt außerhalb der KI-Verordnung.'],
  ] as const)('shows a refused question with its own reason and no note (%s)', async (language, note) => {
    const user = userEvent.setup()
    const reason =
      language === 'de'
        ? 'Diese Frage kann ich nicht beantworten: Das Sprachmodell hat ihre Bearbeitung abgelehnt.'
        : "I can't answer this question: the language model declined to process it."
    serve(() => answered({ kind: 'refused', answer: reason, citations: [] }))
    await openAsk('/app/ask', language)

    await user.type(field(language === 'de' ? 'Ihre Frage' : 'Your question'), 'Q?{Enter}')

    expect(await screen.findByText(reason)).toBeVisible()
    expect(screen.queryByText(note)).toBeNull()
    expect(sent).toHaveLength(1)
  })

  it('lists the texts in German, a text only in English marked as such', async () => {
    serve(() => answered())
    await openAsk('/app/ask', 'de')
    const panel = screen.getByRole('region', { name: 'Grundlage der Antworten' })
    expect(
      await within(panel).findByText('KI-Verordnung, konsolidierte Fassung vom 27. Juli 2026'),
    ).toBeVisible()
    const items = within(panel)
      .getAllByRole('listitem')
      .map((item) => item.textContent)
    expect(items).toEqual([
      'KI-Verordnung, konsolidierte Fassung vom 27. Juli 2026Konsolidierte Fassung',
      'Guidelines on high-risk classificationnur auf EnglischEntwurf',
    ])
  })

  it('has no axe violations with an answer on screen', async () => {
    const user = userEvent.setup()
    serve(() => answered())
    const { container } = renderRoute('/app/ask')
    await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
    await user.type(field(), 'What counts as a deployer?{Enter}')
    await screen.findByText(/A deployer is anyone/)
    expect((await axe(container, AXE_OPTIONS)).violations).toEqual([])
  })
})
