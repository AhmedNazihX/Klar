import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult } from '@/api'
import {
  classificationRunOptions,
  type ClassificationRun,
} from '@/features/classify/classification-store'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { WORKED_EXAMPLE } from '@/test/classify-fixtures'
import {
  ANNEX_IV_ANSWER,
  ANSWERS_URL,
  DEPLOYER_DRAFTS,
  documentsHandlers,
  DRAFTS_URL,
  EXPORT_URL,
  PROVIDER_RESULT,
  WORKERS_TOOL_ANSWER,
  type AnswerRow,
  type DocumentsTraffic,
} from '@/test/documents-fixtures'
import { server } from '@/test/msw-server'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS, inventoryRow, userDataHandlers } from '@/test/user-data-handlers'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

const APPLICANTS = '0b6f7c1e-1111-4a5b-9c3d-000000000001'
const DRIVERS = '0b6f7c1e-2222-4a5b-9c3d-000000000002'
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }

let answerRows: AnswerRow[] = []
let profileSizeClass: string | null = null
let traffic: DocumentsTraffic

beforeEach(() => {
  answerRows = []
  profileSizeClass = null
  traffic = { draftBodies: [], savedAnswers: [], exports: [] }
  server.use(
    ...userDataHandlers(
      () => [inventoryRow({ size_class: profileSizeClass, staff_band: '10-49' })],
      () => 2,
    ),
    ...documentsHandlers(() => answerRows, traffic),
  )
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

type Tool = { toolId: string; name: string; result: ClassificationResult }

const APPLICANT_SCREENING: Tool = {
  toolId: APPLICANTS,
  name: 'Applicant screening',
  result: WORKED_EXAMPLE,
}
const DRIVER_SCORING: Tool = { toolId: DRIVERS, name: 'Driver scoring', result: PROVIDER_RESULT }

async function openDocuments(
  path: string,
  {
    tools = [APPLICANT_SCREENING],
    language = 'en',
  }: { tools?: Tool[]; language?: 'en' | 'de' } = {},
) {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  for (const tool of tools) {
    const run: ClassificationRun = { ...tool, description: 'A tool.' }
    client.setQueryData(classificationRunOptions(tool.toolId).queryKey, run)
  }
  const user = userEvent.setup()
  const rendered = renderRoute(path, client)
  return { user, ...rendered }
}

async function preview(): Promise<HTMLElement> {
  return screen.findByRole('article', { name: 'Document preview' }, { timeout: FIRST_RENDER_MS })
}

describe('Documents list', () => {
  it("lists every tool's documents grouped by tool, with their statuses", async () => {
    profileSizeClass = 'sme'
    await openDocuments('/app/documents', { tools: [APPLICANT_SCREENING, DRIVER_SCORING] })
    const nav = await screen.findByRole('navigation', { name: 'Documents' })
    const applicants = await within(nav).findByRole('region', { name: 'For Applicant screening' })
    expect(
      await within(applicants).findByRole('link', { name: /Human oversight record/ }),
    ).toHaveTextContent('Art. 26(2). Needs 3 answers')
    expect(
      within(applicants).getByRole('link', { name: /Notice to workers' representatives/ }),
    ).toHaveTextContent('Art. 26(7). Needs 4 answers')
    const drivers = within(nav).getByRole('region', { name: 'For Driver scoring' })
    expect(
      await within(drivers).findByRole('link', { name: /Technical documentation \(Annex IV\)/ }),
    ).toHaveTextContent('Art. 11(1). Needs 26 answers')
    const opened = within(applicants).getByRole('link', { name: /Human oversight record/ })
    expect(opened).toHaveAttribute('aria-current', 'page')
    expect(opened).toHaveAttribute('href', `/app/documents/art_26_2_oversight?tool=${APPLICANTS}`)
  })

  it("drafts each tool from its own result with the profile's size class", async () => {
    profileSizeClass = 'sme'
    await openDocuments('/app/documents', { tools: [APPLICANT_SCREENING, DRIVER_SCORING] })
    await preview()
    await vi.waitFor(() => {
      expect(traffic.draftBodies.map((body) => body.result.role).sort()).toEqual([
        'deployer',
        'provider',
      ])
    })
    for (const body of traffic.draftBodies) {
      expect(body).toMatchObject({ language: 'en', size_class: 'sme', answers: {} })
    }
  })

  it('says there is nothing to draft before a tool is classified', async () => {
    await openDocuments('/app/documents', { tools: [] })
    expect(
      await screen.findByText(
        'No documents yet. Classify a tool, and Klar drafts the documents its result calls for.',
        undefined,
        { timeout: FIRST_RENDER_MS },
      ),
    ).toBeInTheDocument()
    const main = screen.getByRole('main')
    expect(within(main).getByRole('link', { name: 'Classify a tool' })).toHaveAttribute(
      'href',
      '/app/classify',
    )
  })

  it('says so when no tool has the document asked for', async () => {
    await openDocuments('/app/documents/annex_iv_technical_documentation')
    expect(
      await screen.findByText(
        'None of your tools has this document. Pick one from the list.',
        undefined,
        { timeout: FIRST_RENDER_MS },
      ),
    ).toBeInTheDocument()
  })
})

describe('A short document', () => {
  it('shows the draft on white with its stamp, sections, sources and what is still to fill in', async () => {
    await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    const article = await preview()
    expect(
      within(article).getByRole('heading', {
        level: 1,
        name: "Notice to workers' representatives",
      }),
    ).toBeInTheDocument()
    expect(within(article).getByText('DRAFT')).toBeInTheDocument()
    expect(article).toHaveTextContent(
      'AI Act as checked: As amended, 2026, applying on 6 October 2026.',
    )
    const system = within(article).getByRole('region', { name: 'What we plan to use' })
    expect(system).toHaveTextContent('The tool reads job applications, scores them')
    expect(system).toHaveTextContent('From your classification')
    const tool = within(article).getByRole('region', { name: 'The tool and its supplier' })
    expect(tool).toHaveTextContent('To fill in. Answer it in the guided interview.')
    expect(article).toHaveTextContent(
      `Draft prepared with Klar. ${DEPLOYER_DRAFTS.en[1]?.document.disclaimer ?? ''}`,
    )
    const checks = screen.getByRole('region', { name: 'Automatic checks' })
    expect(
      within(checks)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      'Every required section is presentPassed',
      "No content you didn't supplyPassed",
      'Facts match the classificationPassed',
    ])
  })

  it('saves an answer under all four key columns and redraws the notice with it', async () => {
    const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    const interview = await screen.findByRole('region', { name: 'Guided interview' })
    expect(interview).toHaveTextContent('0 of 4 answered')
    await user.click(within(interview).getByRole('button', { name: 'Skip for now' }))
    const field = within(interview).getByLabelText('What is the tool called, and who supplies it?')
    expect(interview).toHaveTextContent(
      "Written into the notice as you give it. Klar won't add anything you didn't say.",
    )
    await user.type(field, WORKERS_TOOL_ANSWER)
    await user.click(within(interview).getByRole('button', { name: 'Save answer' }))

    await vi.waitFor(() => {
      expect(traffic.savedAnswers).toEqual([
        {
          body: {
            system_id: APPLICANTS,
            template: 'art_26_7_workers',
            question_key: 'tool_and_supplier',
            answer: WORKERS_TOOL_ANSWER,
          },
          onConflict: 'system_id,user_id,template,question_key',
        },
      ])
    })
    const tool = await within(await preview()).findByText(WORKERS_TOOL_ANSWER)
    expect(tool.closest('section')).toHaveTextContent('From your interview answers')
    expect(traffic.draftBodies.at(-1)?.answers).toEqual({
      art_26_7_workers: { tool_and_supplier: WORKERS_TOOL_ANSWER },
    })
    expect(interview).toHaveTextContent('1 of 4 answered')
    expect(within(interview).getByLabelText('When do you plan to start?')).toBeInTheDocument()
  })

  it('shows a full storage apart from other save failures', async () => {
    server.use(
      http.post(ANSWERS_URL, () =>
        HttpResponse.json(
          { code: 'PT507', message: 'storage full', details: null, hint: null },
          { status: 507 },
        ),
      ),
    )
    const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    const interview = await screen.findByRole('region', { name: 'Guided interview' })
    await user.type(within(interview).getByRole('textbox'), 'The works council.')
    await user.click(within(interview).getByRole('button', { name: 'Save answer' }))
    const alert = await within(interview).findByRole('alert')
    expect(alert).toHaveAttribute('data-failure', 'storage-full')
  })

  it('opens with the answers already given and lets one be changed', async () => {
    answerRows = [
      {
        template: 'art_26_7_workers',
        question_key: 'tool_and_supplier',
        answer: WORKERS_TOOL_ANSWER,
      },
    ]
    const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    const interview = await screen.findByRole('region', { name: 'Guided interview' })
    expect(await within(interview).findByText('1 of 4 answered')).toBeInTheDocument()
    await user.click(
      within(interview).getByRole('button', {
        name: 'Change: What is the tool called, and who supplies it?',
      }),
    )
    expect(
      within(interview).getByLabelText('What is the tool called, and who supplies it?'),
    ).toHaveValue(WORKERS_TOOL_ANSWER)
  })
})

describe('Downloads', () => {
  it('sends one export per click with the result, the answers and the format', async () => {
    const createObjectURL = vi.fn(() => 'blob:file')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL }))
    server.use(
      http.post(EXPORT_URL, async ({ request }) => {
        traffic.exports.push(await request.json())
        return new HttpResponse(new Blob(['%PDF']), {
          headers: { 'Content-Type': 'application/pdf' },
        })
      }),
    )
    const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    await preview()
    await user.click(screen.getByRole('button', { name: 'Download PDF' }))
    await vi.waitFor(() => {
      expect(traffic.exports).toHaveLength(1)
    })
    expect(traffic.exports[0]).toEqual({
      result: JSON.parse(JSON.stringify(WORKED_EXAMPLE)) as unknown,
      template: 'art_26_7_workers',
      language: 'en',
      size_class: null,
      answers: {},
      format: 'pdf',
    })
    await vi.waitFor(() => {
      expect(createObjectURL).toHaveBeenCalledTimes(1)
    })
    await user.click(screen.getByRole('button', { name: 'Download .docx' }))
    await vi.waitFor(() => {
      expect(traffic.exports).toHaveLength(2)
    })
    expect(traffic.exports[1]).toMatchObject({ format: 'docx' })
    vi.unstubAllGlobals()
  })

  it('says when the draft failed its checks, and sends nothing again by itself', async () => {
    server.use(
      http.post(EXPORT_URL, () => {
        traffic.exports.push({})
        return HttpResponse.json({ detail: 'checks' }, { status: 409 })
      }),
    )
    const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    await preview()
    await user.click(screen.getByRole('button', { name: 'Download .docx' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "The draft failed its automatic checks, so it can't be downloaded.",
    )
    expect(traffic.exports).toHaveLength(1)
  })
})

describe('A skeleton', () => {
  it('quotes the requirement above To fill in, shows each status and interviews per section', async () => {
    profileSizeClass = 'sme'
    const { user } = await openDocuments(
      `/app/documents/annex_iv_technical_documentation?tool=${DRIVERS}`,
      { tools: [DRIVER_SCORING] },
    )
    const article = await preview()
    expect(article).toHaveTextContent(
      'A simplified form for SMEs and small mid-caps is expected (Art. 11(1)).',
    )
    const general = within(article).getByRole('region', {
      name: 'General description of the system',
    })
    expect(within(general).getByText('8 questions')).toBeInTheDocument()
    const quote = within(general).getByRole('figure')
    expect(quote).toHaveTextContent('Annex IV 1, English')
    expect(
      quote.compareDocumentPosition(within(general).getByText(/^To fill in\./)) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    const standards = within(article).getByRole('region', { name: 'Standards applied' })
    expect(within(standards).getByText('Needs evidence')).toBeInTheDocument()
    expect(
      within(
        within(article).getByRole('region', { name: 'EU declaration of conformity' }),
      ).getByText('Generated last'),
    ).toBeInTheDocument()
    const system = within(article).getByRole('region', { name: 'The system' })
    expect(within(system).getByText('Drafted')).toBeInTheDocument()
    expect(within(system).queryByRole('figure')).not.toBeInTheDocument()
    const risks = within(article).getByRole('region', { name: 'Risk management system' })
    expect(within(risks).getByText('To fill in')).toBeInTheDocument()

    const interview = screen.getByRole('region', {
      name: 'Interview: General description of the system',
    })
    expect(interview).toHaveTextContent('0 of 8 answered')
    expect(interview).toHaveTextContent(
      "Written in as you give it, as a sentence. Klar won't add anything you didn't say.",
    )
    expect(screen.getByRole('region', { name: 'Before you sign' })).toHaveTextContent(
      'Klar checks the draft; you and your experts check the substance.',
    )
    await user.type(within(interview).getByRole('textbox'), ANNEX_IV_ANSWER)
    await user.click(within(interview).getByRole('button', { name: 'Save answer' }))
    expect(await within(general).findByText('Scores drivers for bonuses.')).toBeInTheDocument()
    expect(within(general).getByText('7 questions')).toBeInTheDocument()
    expect(interview).toHaveTextContent('1 of 8 answered')
  })
})

describe('In German', () => {
  it("names a skeleton's statuses, interview and checks in German", async () => {
    await openDocuments(`/app/documents/annex_iv_technical_documentation?tool=${DRIVERS}`, {
      tools: [DRIVER_SCORING],
      language: 'de',
    })
    const article = await screen.findByRole(
      'article',
      { name: 'Dokumentvorschau' },
      { timeout: FIRST_RENDER_MS },
    )
    // The provider fixture is drafted in English: only the screen's own words are German here.
    const statuses = within(article)
      .getAllByText((_, element) => element?.hasAttribute('data-section-status') ?? false)
      .map((element) => element.textContent)
    expect(new Set(statuses)).toEqual(
      new Set([
        'Entworfen',
        '8 Fragen',
        '4 Fragen',
        '1 Frage',
        'Noch auszufüllen',
        'Nachweise nötig',
        'Wird zuletzt erstellt',
      ]),
    )
    expect(
      screen.getByRole('region', { name: 'Interview: General description of the system' }),
    ).toHaveTextContent(
      'So übernommen, wie Sie es angeben, als Satz. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    )
    expect(screen.getByRole('region', { name: 'Bevor Sie unterschreiben' })).toHaveTextContent(
      'Klar prüft den Entwurf; Sie und Ihre Fachleute prüfen den Inhalt.',
    )
  })

  it('says in German that there is nothing to draft yet', async () => {
    await openDocuments('/app/documents', { tools: [], language: 'de' })
    expect(
      await screen.findByText(
        'Noch keine Dokumente. Stufen Sie ein Tool ein, dann entwirft Klar die Dokumente, die sein Ergebnis verlangt.',
        undefined,
        { timeout: FIRST_RENDER_MS },
      ),
    ).toBeInTheDocument()
    expect(
      within(screen.getByRole('main')).getByRole('link', { name: 'Tool einstufen' }),
    ).toBeInTheDocument()
  })

  it('shows every part of the screen in German', async () => {
    const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`, {
      language: 'de',
    })
    const article = await screen.findByRole(
      'article',
      { name: 'Dokumentvorschau' },
      { timeout: FIRST_RENDER_MS },
    )
    expect(within(article).getByText('ENTWURF')).toBeInTheDocument()
    expect(article).toHaveTextContent(
      'Geprüfte Fassung der KI-Verordnung: Geändert, 2026, gültig am 6. Oktober 2026.',
    )
    expect(article).toHaveTextContent('Aus Ihrer Einstufung')
    expect(article).toHaveTextContent(
      'Noch auszufüllen. Beantworten Sie es im geführten Interview.',
    )
    expect(article).toHaveTextContent('Entwurf erstellt mit Klar.')
    const nav = screen.getByRole('navigation', { name: 'Dokumente' })
    const group = within(nav).getByRole('region', { name: 'Für Applicant screening' })
    expect(
      within(group).getByRole('link', { name: /Nachweis der menschlichen Aufsicht/ }),
    ).toHaveTextContent('Art. 26 Abs. 2. 3 Antworten fehlen')
    const interview = screen.getByRole('region', { name: 'Geführtes Interview' })
    expect(interview).toHaveTextContent('0 von 4 beantwortet')
    expect(interview).toHaveTextContent(
      'So in den Hinweis übernommen, wie Sie es angeben. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    )
    expect(within(interview).getByRole('button', { name: 'Antwort speichern' })).toBeInTheDocument()
    const checks = screen.getByRole('region', { name: 'Automatische Prüfungen' })
    expect(
      within(checks)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      'Alle erforderlichen Abschnitte sind vorhandenBestanden',
      'Kein Inhalt, den Sie nicht angegeben habenBestanden',
      'Die Fakten stimmen mit der Einstufung übereinBestanden',
    ])
    expect(screen.getByRole('button', { name: '.docx herunterladen' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PDF herunterladen' })).toBeInTheDocument()
    await user.click(within(interview).getByRole('button', { name: 'Später beantworten' }))
    expect(traffic.draftBodies.at(-1)?.language).toBe('de')
  })
})

describe('Accessibility', () => {
  it('passes axe on a skeleton and on a notice', async () => {
    profileSizeClass = 'sme'
    const { container, unmount } = await openDocuments(
      `/app/documents/annex_iv_technical_documentation?tool=${DRIVERS}`,
      { tools: [APPLICANT_SCREENING, DRIVER_SCORING] },
    )
    await preview()
    expect((await axe(container, AXE_OPTIONS)).violations).toEqual([])
    unmount()
    const notice = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    await preview()
    expect((await axe(notice.container, AXE_OPTIONS)).violations).toEqual([])
  })
})

describe('Drafting fails', () => {
  it('names the tool whose documents could not be drafted and offers to try again', async () => {
    let calls = 0
    server.use(
      http.post(DRAFTS_URL, () => {
        calls += 1
        return HttpResponse.json({ detail: 'down' }, { status: 503 })
      }),
    )
    const { user } = await openDocuments('/app/documents')
    const group = await screen.findByRole(
      'region',
      { name: 'For Applicant screening' },
      { timeout: FIRST_RENDER_MS },
    )
    expect(await within(group).findByRole('alert')).toHaveTextContent(
      "Klar couldn't draft this tool's documents.",
    )
    expect(calls).toBe(1)
    await user.click(within(group).getByRole('button', { name: 'Try again' }))
    await vi.waitFor(() => {
      expect(calls).toBe(2)
    })
  })
})
