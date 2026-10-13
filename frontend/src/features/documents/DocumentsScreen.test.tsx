import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type { ClassificationResult } from '@/api'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { WORKED_EXAMPLE } from '@/test/classify-fixtures'
import {
  ANNEX_IV_ANSWER,
  ANSWERS_URL,
  ART_50_3_CHOICE,
  DEPLOYER_DOCUMENTS,
  DRAFT_URL,
  documentsHandlers,
  EXPORT_URL,
  LIMITED_RESULT,
  LIST_URL,
  newTraffic,
  PROVIDER_RESULT,
  WORKERS_TOOL_ANSWER,
  type AnswerRow,
  type DocumentsTraffic,
} from '@/test/documents-fixtures'
import { INVENTORY_TOOLS_URL, toolRow } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { inventoryRow, userDataHandlers } from '@/test/user-data-handlers'

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
const MOODS = '0b6f7c1e-3333-4a5b-9c3d-000000000003'
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } }

let answerRows: AnswerRow[] = []
let profileSizeClass: string | null = null
let toolRows: Record<string, unknown>[] = []
let traffic: DocumentsTraffic

beforeEach(() => {
  answerRows = []
  profileSizeClass = null
  toolRows = []
  traffic = newTraffic()
  server.use(
    ...userDataHandlers(
      () => [inventoryRow({ size_class: profileSizeClass, staff_band: '10-49' })],
      () => toolRows.length,
      () => toolRows,
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
const MOOD_METER: Tool = { toolId: MOODS, name: 'Mood meter', result: LIMITED_RESULT }

/** Opens `path` with `tools` in the user's inventory (inventory_tools rows, P6). */
async function openDocuments(
  path: string,
  {
    tools = [APPLICANT_SCREENING],
    language = 'en',
  }: { tools?: Tool[]; language?: 'en' | 'de' } = {},
) {
  await i18n.changeLanguage(language)
  toolRows = tools.map((tool) => toolRow(tool.name, tool.result, { id: tool.toolId }))
  const user = userEvent.setup()
  const rendered = renderRoute(path, createTestQueryClient())
  return { user, ...rendered }
}

async function preview(name = 'Document preview'): Promise<HTMLElement> {
  return screen.findByRole('article', { name })
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

  it("lists each inventory tool from its own result and drafts only the open document, with the profile's size class", async () => {
    profileSizeClass = 'sme'
    await openDocuments('/app/documents', { tools: [APPLICANT_SCREENING, DRIVER_SCORING] })
    await preview()
    await vi.waitFor(() => {
      expect(traffic.listBodies.map((body) => body.result.role).sort()).toEqual([
        'deployer',
        'provider',
      ])
    })
    await vi.waitFor(() => {
      expect(traffic.draftBodies.at(-1)).toMatchObject({ size_class: 'sme' })
    })
    expect(new Set(traffic.draftBodies.map((body) => body.template))).toEqual(
      new Set(['art_26_2_oversight']),
    )
    for (const body of traffic.draftBodies) {
      expect(body).toMatchObject({ language: 'en', answers: {} })
    }
  })

  it("sends a document's draft only that document's answers", async () => {
    answerRows = [
      { template: 'art_26_7_workers', question_key: 'tool_and_supplier', answer: 'TalentRank.' },
      { template: 'art_26_2_oversight', question_key: 'tool_and_supplier', answer: 'Other.' },
    ]
    await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    await preview()
    expect(traffic.draftBodies.map((body) => [body.template, body.answers])).toEqual([
      ['art_26_7_workers', { tool_and_supplier: 'TalentRank.' }],
    ])
  })

  it.each([
    ['en', 'Documents', /^Documents \(\d+\)$/],
    ['de', 'Dokumente', /^Dokumente \(\d+\)$/],
  ] as const)(
    'names the list toggle without a count until every list is in (%s)',
    async (language, loading, counted) => {
      let release = (): void => undefined
      const gate = new Promise<void>((resolve) => {
        release = resolve
      })
      // Held, then passed on to the fixture's own list handler.
      server.use(http.post(LIST_URL, async () => gate))
      await openDocuments('/app/documents', { language })
      const toggle = await screen.findByRole('button', { name: loading })
      expect(toggle).not.toHaveTextContent(/\(0\)/)
      release()
      await vi.waitFor(() => {
        expect(toggle).toHaveAccessibleName(counted)
      })
    },
  )

  it('says there is nothing to draft before a tool is classified', async () => {
    await openDocuments('/app/documents', { tools: [] })
    expect(
      await screen.findByText(
        'No documents yet. Classify a tool, and Klar drafts the documents its result calls for.',
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
      await screen.findByText('None of your tools has this document. Pick one from the list.'),
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
    const disclaimer = DEPLOYER_DOCUMENTS.en.art_26_7_workers?.document.disclaimer ?? ''
    expect(article).toHaveTextContent(`Draft prepared with Klar. ${disclaimer}`)
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

  it('saves an answer under the inventory tool and all four key columns, and redraws the notice with it', async () => {
    const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    await preview()
    const interview = screen.getByRole('region', { name: 'Guided interview' })
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
    expect(traffic.draftBodies.at(-1)?.answers).toEqual({ tool_and_supplier: WORKERS_TOOL_ANSWER })
    expect(interview).toHaveTextContent('1 of 4 answered')
    expect(within(interview).getByLabelText('When do you plan to start?')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Documents' })
    expect(
      within(nav).getByRole('link', { name: /Notice to workers' representatives/ }),
    ).toHaveTextContent('Art. 26(7). Needs 3 answers')
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
    await preview()
    const interview = screen.getByRole('region', { name: 'Guided interview' })
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
    await preview()
    const interview = screen.getByRole('region', { name: 'Guided interview' })
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

describe('The Art. 50(3) disclosure', () => {
  it('asks which the system does and drafts the notice for the choice, saved as its key', async () => {
    const { user } = await openDocuments(`/app/documents/art_50_3_disclosure?tool=${MOODS}`, {
      tools: [MOOD_METER],
    })
    const article = await preview()
    expect(within(article).getByRole('region', { name: 'The disclosure' })).toHaveTextContent(
      'To fill in. Answer it in the guided interview.',
    )
    const interview = screen.getByRole('region', { name: 'Guided interview' })
    const choice = within(interview).getByRole('group', {
      name: 'Does the system recognise emotions, sort people into categories from biometric data, or both?',
    })
    expect(
      within(choice)
        .getAllByRole('radio')
        .map((radio) => radio.closest('label')?.textContent),
    ).toEqual([
      'It recognises emotions or intentions from biometric data',
      'It sorts people into categories from biometric data',
      'Both',
    ])
    // The choice's hint names no document: this one is a disclosure, not a notice.
    expect(choice).toHaveAccessibleDescription(
      'Klar writes its own set wording for what you pick.',
    )
    await user.click(within(choice).getByRole('radio', { name: 'Both' }))
    await user.click(within(interview).getByRole('button', { name: 'Save answer' }))
    await vi.waitFor(() => {
      expect(traffic.savedAnswers.map((saved) => saved.body)).toEqual([
        {
          system_id: MOODS,
          template: 'art_50_3_disclosure',
          question_key: 'recognises',
          answer: ART_50_3_CHOICE,
        },
      ])
    })
    expect(
      await within(await preview()).findByText(
        'An AI system for emotion recognition and biometric categorisation is in operation here.',
      ),
    ).toBeInTheDocument()
  })

  it.each([
    ['en', 'Disclosure: emotion recognition and biometric categorisation'],
    ['de', 'Hinweis: Emotionserkennung und biometrische Kategorisierung'],
  ] as const)(
    'names in its title and list entry only what the choice picked (%s)',
    async (language, title) => {
      answerRows = [
        { template: 'art_50_3_disclosure', question_key: 'recognises', answer: ART_50_3_CHOICE },
      ]
      await openDocuments(`/app/documents/art_50_3_disclosure?tool=${MOODS}`, {
        tools: [MOOD_METER],
        language,
      })
      const nav = await screen.findByRole('navigation', {
        name: language === 'de' ? 'Dokumente' : 'Documents',
      })
      expect(await within(nav).findByRole('link', { name: new RegExp(title) })).toHaveAttribute(
        'aria-current',
        'page',
      )
      expect(within(nav).queryByText(/ oder | or /)).not.toBeInTheDocument()
      // The draft's own title, as the drafter writes it in the screen's language.
      const article = await preview(language === 'de' ? 'Dokumentvorschau' : 'Document preview')
      expect(within(article).getByRole('heading', { level: 1 })).toHaveTextContent(title)
      expect(article).toHaveTextContent(
        language === 'de'
          ? 'Hier ist ein KI-System zur Emotionserkennung und biometrischen'
          : 'An AI system for emotion recognition and biometric categorisation',
      )
    },
  )

  it('asks the choice in German', async () => {
    await openDocuments(`/app/documents/art_50_3_disclosure?tool=${MOODS}`, {
      tools: [MOOD_METER],
      language: 'de',
    })
    await preview('Dokumentvorschau')
    const interview = screen.getByRole('region', { name: 'Geführtes Interview' })
    const choice = within(interview).getByRole('group', {
      name: 'Erkennt das System Emotionen, ordnet es Personen anhand biometrischer Daten Kategorien zu oder beides?',
    })
    expect(
      within(choice)
        .getAllByRole('radio')
        .map((radio) => radio.closest('label')?.textContent),
    ).toEqual([
      'Es erkennt Emotionen oder Absichten anhand biometrischer Daten',
      'Es ordnet Personen anhand biometrischer Daten Kategorien zu',
      'Beides',
    ])
    expect(interview).toHaveTextContent('Für Ihre Auswahl übernimmt Klar einen festen Wortlaut.')
  })
})

describe('Downloads', () => {
  it("sends one export per click with the result, the document's own answers, the profile's size class and the format", async () => {
    profileSizeClass = 'smc'
    answerRows = [
      {
        template: 'art_26_7_workers',
        question_key: 'tool_and_supplier',
        answer: WORKERS_TOOL_ANSWER,
      },
      { template: 'art_26_2_oversight', question_key: 'overseers', answer: 'Another document.' },
    ]
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
    await vi.waitFor(() => {
      expect(traffic.draftBodies.at(-1)?.size_class).toBe('smc')
    })
    await user.click(screen.getByRole('button', { name: 'Download PDF' }))
    await vi.waitFor(() => {
      expect(traffic.exports).toHaveLength(1)
    })
    expect(traffic.exports[0]).toEqual({
      result: JSON.parse(JSON.stringify(WORKED_EXAMPLE)) as unknown,
      template: 'art_26_7_workers',
      language: 'en',
      size_class: 'smc',
      answers: { tool_and_supplier: WORKERS_TOOL_ANSWER },
      format: 'pdf',
    })
    await vi.waitFor(() => {
      expect(createObjectURL).toHaveBeenCalledTimes(1)
    })
    await user.click(screen.getByRole('button', { name: 'Download .docx' }))
    await vi.waitFor(() => {
      expect(traffic.exports).toHaveLength(2)
    })
    expect(traffic.exports[1]).toMatchObject({ format: 'docx', size_class: 'smc' })
    vi.unstubAllGlobals()
  })

  it.each([
    [409, 'en', "The draft failed its automatic checks, so it can't be downloaded."],
    [
      409,
      'de',
      'Der Entwurf hat die automatischen Prüfungen nicht bestanden und kann nicht heruntergeladen werden.',
    ],
    [413, 'en', 'This document is too long to make into a file. Please shorten some answers.'],
    [413, 'de', 'Dieses Dokument ist zu lang für eine Datei. Bitte kürzen Sie einige Antworten.'],
    [503, 'en', 'Klar is busy making other files. Please try again in a moment.'],
    [503, 'de', 'Klar erstellt gerade andere Dateien. Bitte versuchen Sie es gleich noch einmal.'],
    [
      504,
      'en',
      'Making this file took too long. Please try again; if it happens again, shorten some answers.',
    ],
    [
      504,
      'de',
      'Das Erstellen der Datei hat zu lange gedauert. Bitte versuchen Sie es erneut; wenn es wieder passiert, kürzen Sie einige Antworten.',
    ],
    [500, 'en', "Klar couldn't make the file. Please try again."],
  ] as const)(
    'says why a %i made no file (%s), and sends nothing again by itself',
    async (status, language, message) => {
      server.use(
        http.post(EXPORT_URL, () => {
          traffic.exports.push({})
          return HttpResponse.json({ detail: 'refused' }, { status })
        }),
      )
      const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`, {
        language,
      })
      await preview(language === 'de' ? 'Dokumentvorschau' : 'Document preview')
      const name = language === 'de' ? '.docx herunterladen' : 'Download .docx'
      await user.click(screen.getByRole('button', { name }))
      expect(await screen.findByRole('alert')).toHaveTextContent(message)
      expect(traffic.exports).toHaveLength(1)
    },
  )
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
      "Annex IV 1: General description of the system. Written in as you give it, as a sentence. Klar won't add anything you didn't say.",
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

  it('has the DocSkeleton heading and its numbered sections, each with its status', async () => {
    await openDocuments(`/app/documents/annex_iv_technical_documentation?tool=${DRIVERS}`, {
      tools: [DRIVER_SCORING],
    })
    const article = await preview()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Technical documentation')
    expect(within(article).getByRole('heading', { level: 2, name: /\(Annex IV\)/ })).toBeVisible()
    expect(
      screen.getByText(
        'Annex IV, for Driver scoring. Klar fills in what it knows and asks you for the rest.',
      ),
    ).toBeInTheDocument()
    const progress = screen.getByRole('progressbar', { name: '2 of 11 sections drafted' })
    expect(progress).toHaveAttribute('aria-valuenow', '2')
    expect(progress).toHaveAttribute('aria-valuemax', '11')
    const sections = screen.getByRole('navigation', { name: 'Annex IV sections' })
    const links = within(sections).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual([
      '1The systemDrafted',
      '2Its classificationDrafted',
      '3General description of the system8 questions',
      '4Elements and development process8 questions',
      '5Monitoring, functioning and control4 questions',
      '6Performance metrics1 question',
      '7Risk management systemTo fill in',
      '8Changes through the lifecycleTo fill in',
      '9Standards appliedNeeds evidence',
      '10EU declaration of conformityGenerated last',
      '11Post-market monitoringTo fill in',
    ])
    expect(links[2]).toHaveAttribute('href', '#section-general_description')
    expect(within(article).getByRole('region', { name: 'General description of the system' })).toBe(
      document.getElementById('section-general_description'),
    )
  })

  it('has the DocSkeleton heading in German, and the Art. 17 duty named as German cites it', async () => {
    await openDocuments(`/app/documents/art_17_quality_management?tool=${DRIVERS}`, {
      tools: [DRIVER_SCORING],
      language: 'de',
    })
    await preview('Dokumentvorschau')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Qualitätsmanagementsystem')
    expect(
      screen.getByText(
        'Art. 17, für Driver scoring. Klar füllt aus, was es weiß, und fragt Sie nach dem Rest.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('progressbar', { name: '2 von 15 Abschnitten entworfen' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Abschnitte nach Art. 17' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Dokumente' })
    expect(
      within(nav).getByRole('link', { name: /Qualitätsmanagementsystem \(Art\. 17\)/ }),
    ).toHaveTextContent('Art. 16 Buchst. c. 13 Antworten fehlen')
  })

  it('keeps a short document without the skeleton heading or section list', async () => {
    await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`)
    const article = await preview()
    expect(within(article).getByRole('heading', { level: 1 })).toHaveTextContent(
      "Notice to workers' representatives",
    )
    expect(screen.queryByRole('navigation', { name: /sections/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('progressbar', { name: /sections drafted/ })).not.toBeInTheDocument()
  })
})

describe('The hint names what the answer is written into', () => {
  it.each([
    ['en', "Written into the record as you give it. Klar won't add anything you didn't say."],
    [
      'de',
      'So in den Nachweis übernommen, wie Sie es angeben. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    ],
  ] as const)('a record (%s)', async (language, hint) => {
    await openDocuments(`/app/documents/art_26_2_oversight?tool=${APPLICANTS}`, { language })
    await preview(language === 'de' ? 'Dokumentvorschau' : 'Document preview')
    const interview = screen.getByRole('region', {
      name: language === 'de' ? 'Geführtes Interview' : 'Guided interview',
    })
    expect(interview).toHaveTextContent(hint)
  })

  it('a disclosure, once its choice is made', async () => {
    answerRows = [
      { template: 'art_50_3_disclosure', question_key: 'recognises', answer: ART_50_3_CHOICE },
    ]
    await openDocuments(`/app/documents/art_50_3_disclosure?tool=${MOODS}`, {
      tools: [MOOD_METER],
    })
    await preview()
    expect(screen.getByRole('region', { name: 'Guided interview' })).toHaveTextContent(
      "Written into the disclosure as you give it. Klar won't add anything you didn't say.",
    )
  })
})

describe('In German', () => {
  it("names a skeleton's statuses, interview and checks in German", async () => {
    await openDocuments(`/app/documents/annex_iv_technical_documentation?tool=${DRIVERS}`, {
      tools: [DRIVER_SCORING],
      language: 'de',
    })
    const article = await preview('Dokumentvorschau')
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
      'Anhang IV Nr. 1: General description of the system. So übernommen, wie Sie es angeben, als Satz. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    )
    expect(screen.getByRole('region', { name: 'Bevor Sie unterschreiben' })).toHaveTextContent(
      'Klar prüft den Entwurf; Sie und Ihre Fachleute prüfen den Inhalt.',
    )
  })

  it('names a skeleton without its provision in the title in both languages', () => {
    const tool = 'Driver scoring'
    expect([
      i18n.t('documents.skeleton.introNoSource', { lng: 'en', tool }),
      i18n.t('documents.skeleton.introNoSource', { lng: 'de', tool }),
      i18n.t('documents.skeleton.sectionsPlain', { lng: 'en' }),
      i18n.t('documents.skeleton.sectionsPlain', { lng: 'de' }),
    ]).toEqual([
      'For Driver scoring. Klar fills in what it knows and asks you for the rest.',
      'Für Driver scoring. Klar füllt aus, was es weiß, und fragt Sie nach dem Rest.',
      'Sections',
      'Abschnitte',
    ])
  })

  it('says in German that there is nothing to draft yet', async () => {
    await openDocuments('/app/documents', { tools: [], language: 'de' })
    expect(
      await screen.findByText(
        'Noch keine Dokumente. Stufen Sie ein Tool ein, dann entwirft Klar die Dokumente, die sein Ergebnis verlangt.',
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
    const article = await preview('Dokumentvorschau')
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

  it('names the loading states in both languages', () => {
    expect([
      i18n.t('documents.draftingOne', { lng: 'en' }),
      i18n.t('documents.draftingOne', { lng: 'de' }),
    ]).toEqual(['Drafting the document…', 'Das Dokument wird entworfen …'])
    expect([
      i18n.t('documents.toolsLoading', { lng: 'en' }),
      i18n.t('documents.toolsLoading', { lng: 'de' }),
    ]).toEqual(['Loading your tools…', 'Ihre Tools werden geladen …'])
  })
})

describe('Accessibility', () => {
  it('passes axe on a skeleton, a notice and a choice question', async () => {
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
    notice.unmount()
    const choice = await openDocuments(`/app/documents/art_50_3_disclosure?tool=${MOODS}`, {
      tools: [MOOD_METER],
    })
    await preview()
    expect((await axe(choice.container, AXE_OPTIONS)).violations).toEqual([])
  })
})

describe('A stored result the API can’t read', () => {
  it.each([
    [
      'en',
      'For Applicant screening',
      "Klar can't read this tool's saved result, so it can't draft its documents. Run the tool's checks again.",
    ],
    [
      'de',
      'Für Applicant screening',
      'Klar kann das gespeicherte Ergebnis dieses Tools nicht lesen und deshalb keine Dokumente dafür entwerfen. Führen Sie die Prüfungen für das Tool erneut durch.',
    ],
  ] as const)(
    'says so beside the tool and offers no retry (%s)',
    async (language, region, line) => {
      let calls = 0
      server.use(
        http.post(LIST_URL, () => {
          calls += 1
          return HttpResponse.json({ detail: 'invalid' }, { status: 422 })
        }),
      )
      await openDocuments('/app/documents', { language })
      const group = await screen.findByRole('region', { name: region })
      expect(await within(group).findByRole('alert')).toHaveTextContent(line)
      expect(within(group).queryByRole('button')).toBeNull()
      expect(calls).toBe(1)
    },
  )
})

describe('Something fails', () => {
  it('names the tool whose documents could not be listed and offers to try again', async () => {
    let calls = 0
    server.use(
      http.post(LIST_URL, () => {
        calls += 1
        return HttpResponse.json({ detail: 'down' }, { status: 503 })
      }),
    )
    const { user } = await openDocuments('/app/documents')
    const group = await screen.findByRole('region', { name: 'For Applicant screening' })
    expect(await within(group).findByRole('alert')).toHaveTextContent(
      "Klar couldn't draft this tool's documents.",
    )
    expect(calls).toBe(1)
    await user.click(within(group).getByRole('button', { name: 'Try again' }))
    await vi.waitFor(() => {
      expect(calls).toBe(2)
    })
  })

  it.each([
    [
      413,
      'en',
      "This document's answers are too long to send together. Please shorten some answers.",
    ],
    [
      413,
      'de',
      'Die Antworten zu diesem Dokument sind zusammen zu lang. Bitte kürzen Sie einige Antworten.',
    ],
    [503, 'en', "Klar couldn't draft this document."],
    [503, 'de', 'Klar konnte dieses Dokument nicht entwerfen.'],
  ] as const)(
    'says why a %i drafted no document (%s), and tries again only when asked',
    async (status, language, message) => {
      let calls = 0
      server.use(
        http.post(DRAFT_URL, () => {
          calls += 1
          return HttpResponse.json({ detail: 'refused' }, { status })
        }),
      )
      const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`, {
        language,
      })
      const main = await screen.findByRole('main')
      expect(await within(main).findByRole('alert')).toHaveTextContent(message)
      expect(calls).toBe(1)
      await user.click(
        within(main).getByRole('button', {
          name: language === 'de' ? 'Erneut versuchen' : 'Try again',
        }),
      )
      await vi.waitFor(() => {
        expect(calls).toBe(2)
      })
    },
  )

  it.each([
    {
      language: 'en',
      alert: "This document's answers are too long to send together. Please shorten some answers.",
      title: 'Guided interview',
      progress: '1 of 4 answered',
      hint: "Written into the notice as you give it. Klar won't add anything you didn't say.",
      change: 'Change: Is there a works council? Who receives this notice?',
      save: 'Save answer',
    },
    {
      language: 'de',
      alert:
        'Die Antworten zu diesem Dokument sind zusammen zu lang. Bitte kürzen Sie einige Antworten.',
      title: 'Geführtes Interview',
      progress: '1 von 4 beantwortet',
      hint: 'So in den Hinweis übernommen, wie Sie es angeben. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
      change: 'Ändern: Gibt es einen Betriebsrat? Wer erhält diese Information?',
      save: 'Antwort speichern',
    },
  ] as const)(
    'keeps the interview when the answers are too long to draft, so one can be shortened ($language)',
    async ({ language, alert, title, progress, hint, change, save }) => {
      answerRows = [
        { template: 'art_26_7_workers', question_key: 'recipients', answer: 'x'.repeat(20_000) },
      ]
      server.use(
        http.post(DRAFT_URL, () => HttpResponse.json({ detail: 'too large' }, { status: 413 })),
      )
      const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`, {
        language,
      })
      const main = await screen.findByRole('main')
      expect(await within(main).findByRole('alert')).toHaveTextContent(alert)
      const interview = await screen.findByRole('region', { name: title })
      expect(interview).toHaveTextContent(progress)
      expect(interview).toHaveTextContent(hint)
      await user.click(within(interview).getByRole('button', { name: change }))
      const field = within(interview).getByRole('textbox')
      expect(field).toHaveValue('x'.repeat(20_000))
      expect(field.tagName).toBe('TEXTAREA')
      await user.clear(field)
      await user.type(field, 'The works council.')
      await user.click(within(interview).getByRole('button', { name: save }))
      await vi.waitFor(() => {
        expect(traffic.savedAnswers.map((saved) => saved.body)).toEqual([
          {
            system_id: APPLICANTS,
            template: 'art_26_7_workers',
            question_key: 'recipients',
            answer: 'The works council.',
          },
        ])
      })
    },
  )

  it.each([
    [
      'en',
      "Klar couldn't draft this document.",
      "The draft shown doesn't hold your latest answers yet.",
    ],
    [
      'de',
      'Klar konnte dieses Dokument nicht entwerfen.',
      'Der angezeigte Entwurf enthält Ihre neuesten Antworten noch nicht.',
    ],
  ] as const)(
    'says when the draft after a save failed and the one on show is stale (%s)',
    async (language, message, stale) => {
      let drafts = 0
      server.use(
        http.post(DRAFT_URL, () => {
          drafts += 1
          // The first draft comes from the fixtures; the one after the save fails.
          return drafts > 1 ? HttpResponse.json({ detail: 'busy' }, { status: 503 }) : undefined
        }),
      )
      const { user } = await openDocuments(`/app/documents/art_26_7_workers?tool=${APPLICANTS}`, {
        language,
      })
      const article = await preview(language === 'de' ? 'Dokumentvorschau' : 'Document preview')
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      const interview = screen.getByRole('region', {
        name: language === 'de' ? 'Geführtes Interview' : 'Guided interview',
      })
      await user.type(within(interview).getByRole('textbox'), 'The works council.')
      await user.click(
        within(interview).getByRole('button', {
          name: language === 'de' ? 'Antwort speichern' : 'Save answer',
        }),
      )
      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(message)
      expect(alert).toHaveTextContent(stale)
      expect(drafts).toBe(2)
      expect(article).toBeInTheDocument()
    },
  )

  it.each([
    ['en', "Klar couldn't load your tools."],
    ['de', 'Klar konnte Ihre Tools nicht laden.'],
  ] as const)('says when the tools could not be loaded (%s)', async (language, message) => {
    server.use(http.get(INVENTORY_TOOLS_URL, () => HttpResponse.json({}, { status: 500 })))
    await openDocuments('/app/documents', { language })
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })
})
