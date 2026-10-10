import { QueryClient } from '@tanstack/react-query'
import { getDefaultNormalizer, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { WORKED_EXAMPLE } from '@/test/classify-fixtures'
import { inventoryToolsHandler, toolRow } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import { env } from '@/lib/env'
import { FIRST_RENDER_MS, INVENTORIES_URL } from '@/test/user-data-handlers'
import {
  COUNTS_URL,
  createUserDataStore,
  DELETE_URL,
  EXPORT_URL,
  type StoredInventory,
  type UserDataStore,
} from '@/test/your-data-store'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

// One inventory with a profile, two tools, three runs, two interview answers and a duty tick:
// every kind of row Your data counts differs, so a swapped count shows.
const SAVED: StoredInventory[] = [
  {
    name: 'AI inventory',
    company_name: 'Nordwerk Logistik GmbH',
    staff_band: '10-49',
    turnover_band: 'up_to_10m',
    established_in: 'DE',
    used_in: 'eu',
    created_at: '2026-09-30T09:00:00+00:00',
    systems: [
      {
        name: 'CV screener',
        description: 'Ranks applicants by their CV.',
        created_at: '2026-09-30T09:05:00+00:00',
        classifications: [
          { run_no: 1, risk_class: 'high_risk', status: 'decided', law_version: 'amended' },
          { run_no: 2, risk_class: 'high_risk', status: 'decided', law_version: 'original' },
        ],
        interview_answers: [
          { template: 'annex_iv', question_key: 'purpose', answer: 'Shortlisting.' },
          { template: 'annex_iv', question_key: 'oversight', answer: 'A recruiter checks.' },
        ],
        duty_progress: [{ obligation_key: 'art_26_1', created_at: '2026-10-01T09:00:00+00:00' }],
      },
      {
        name: 'Chat assistant',
        description: 'Answers customer questions.',
        created_at: '2026-09-30T10:00:00+00:00',
        classifications: [
          { run_no: 1, risk_class: 'limited_risk', status: 'decided', law_version: 'amended' },
        ],
        interview_answers: [],
        duty_progress: [],
      },
    ],
  },
]

// One tool with a run, a document answer and two duty ticks, and no company profile: the
// singular forms, a plural, and kinds left out of the delete dialog's count.
const ONE_OF_EACH: StoredInventory[] = [
  {
    name: 'AI inventory',
    company_name: null,
    staff_band: null,
    turnover_band: null,
    established_in: null,
    used_in: null,
    created_at: '2026-09-30T09:00:00+00:00',
    systems: [
      {
        name: 'CV screener',
        description: 'Ranks applicants by their CV.',
        created_at: '2026-09-30T09:05:00+00:00',
        classifications: [
          { run_no: 1, risk_class: 'high_risk', status: 'decided', law_version: 'amended' },
        ],
        interview_answers: [
          { template: 'annex_iv', question_key: 'purpose', answer: 'Shortlisting.' },
        ],
        duty_progress: [
          { obligation_key: 'art_26_1', created_at: '2026-10-01T09:00:00+00:00' },
          { obligation_key: 'art_26_2', created_at: '2026-10-01T09:05:00+00:00' },
        ],
      },
    ],
  },
]

// A company profile and nothing else: the dialog's list is only "your company profile".
const PROFILE_ONLY: StoredInventory[] = [
  {
    name: 'AI inventory',
    company_name: 'Nordwerk Logistik GmbH',
    staff_band: null,
    turnover_band: null,
    established_in: null,
    used_in: null,
    created_at: '2026-09-30T09:00:00+00:00',
    systems: [],
  },
]

// The space the counts keep with their nouns, so a line never breaks between them.
const NBSP = '\u00a0'

let store: UserDataStore
// What the browser was asked to save: the file and its name.
let downloads: { blob: Blob; fileName: string }[] = []
let lastBlob: Blob | null = null

beforeAll(() => {
  // jsdom has neither object URLs nor modal dialogs; these stand in for the browser's.
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: (blob: Blob) => {
      lastBlob = blob
      return 'blob:klar-test'
    },
  })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: () => undefined })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    if (lastBlob) downloads.push({ blob: lastBlob, fileName: this.download })
  })
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
  downloads = []
  lastBlob = null
  store = createUserDataStore(SAVED)
  server.use(...store.handlers)
})

afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

async function openYourData(language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  const rendered = renderRoute('/app/your-data')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
  return { user, ...rendered }
}

function panel(name: string): HTMLElement {
  return screen.getByRole('region', { name })
}

/** Picks the data file (JSON) in "Download everything" and downloads it. */
async function downloadData(
  user: ReturnType<typeof userEvent.setup>,
  language: 'en' | 'de' = 'en',
): Promise<void> {
  const [choice, button] =
    language === 'de'
      ? ['Daten (JSON): alles, maschinenlesbar', 'Herunterladen']
      : ['Data (JSON): everything, machine-readable', 'Download']
  await user.click(screen.getByRole('radio', { name: choice }))
  await user.click(screen.getByRole('button', { name: button }))
}

/** The count shown beside a row's label in "What Klar keeps". */
function countOf(label: string): string | null {
  return screen.getByText(label).nextElementSibling?.textContent ?? null
}

/** Opens the delete dialog from its panel (named the same as its button). */
async function openDeleteDialog(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(within(panel(name)).getByRole('button', { name }))
}

/** The delete dialog's loss text, matched as written: its non-breaking spaces must be there. */
function lossText(dialogName: string, text: string): HTMLElement {
  return within(screen.getByRole('dialog', { name: dialogName })).getByText(text, {
    normalizer: getDefaultNormalizer({ collapseWhitespace: false }),
  })
}

async function deleteEverything(user: ReturnType<typeof userEvent.setup>, word = 'DELETE') {
  await user.click(within(panel('Delete my data')).getByRole('button', { name: 'Delete my data' }))
  await user.type(screen.getByLabelText(`Type ${word} to confirm`), word)
  await user.click(screen.getByRole('button', { name: 'Delete everything' }))
}

describe('Your data, what Klar keeps and who processes it', () => {
  it('counts each kind of stored data and shows the storage used and the 30-day deletion', async () => {
    await openYourData()
    const keep = panel('What Klar keeps')
    await vi.waitFor(() => expect(countOf('Tools and their descriptions')).toBe('2'))
    expect(countOf('Classification results')).toBe('3')
    expect(countOf('Answers for your draft documents')).toBe('2')
    expect(countOf('Ticked duties on your checklists')).toBe('1')
    expect(countOf('Company profile')).toBe('1')
    expect(within(keep).getByText('< 1 kB of 4 MB storage used')).toBeInTheDocument()
    expect(
      within(keep).getByText(
        'Deleted automatically after 30 days without activity. Never used to train models.',
      ),
    ).toBeInTheDocument()
    // Q&A is session-only and drafts aren't stored (decision 026 item 6; P19).
    expect(within(keep).queryByText(/questions asked/i)).toBeNull()
    expect(within(keep).queryByText('Draft documents')).toBeNull()
    expect(within(keep).getAllByRole('term')).toHaveLength(5)
  })

  it('names OpenRouter, the EU model hosts, Nebius and Supabase, and links the privacy notice', async () => {
    await openYourData()
    const who = panel('Who processes it')
    expect(within(who).getByText('Language models, through OpenRouter')).toBeInTheDocument()
    expect(
      within(who).getByText(
        'OpenRouter passes each request on; its own processing isn’t limited to the EU. The ' +
          'models run in EU regions on Microsoft Azure and Google Vertex AI.',
      ),
    ).toBeInTheDocument()
    // Decision 033 › Privacy wording, verbatim (widened to questions, user 2026-10-10).
    expect(
      within(who).getByText(
        "If Microsoft Azure's content filter blocks a check or a question to Klar, that " +
          'request (for a check: the description and the facts and answers taken from it; for ' +
          "a question: the question and the result it's about, if any) is sent once more to " +
          'Gemini 3.1 Flash-Lite on Google Vertex AI in the EU (zero data retention, no ' +
          'training), for each request the filter blocked. This happens only when the filter ' +
          'blocks it.',
      ),
    ).toBeInTheDocument()
    expect(
      within(who).getByText('Nebius, in the EU, turns your description into a search of the Act.'),
    ).toBeInTheDocument()
    expect(within(who).getByText('Supabase')).toBeInTheDocument()
    expect(
      within(who).getByText(
        'Every request to a model is sent with zero data retention and no training.',
      ),
    ).toBeInTheDocument()
    expect(within(who).getByRole('link', { name: 'Read the privacy notice' })).toHaveAttribute(
      'href',
      '/privacy',
    )
  })

  it('reads the same in German', async () => {
    await openYourData('de')
    expect(screen.getByRole('heading', { level: 1, name: 'Ihre Daten' })).toBeInTheDocument()
    const keep = panel('Was Klar speichert')
    await vi.waitFor(() => expect(countOf('Tools und ihre Beschreibungen')).toBe('2'))
    expect(countOf('Ergebnisse der Einstufung')).toBe('3')
    expect(
      within(keep).getByText(
        'Wird nach 30 Tagen ohne Aktivität automatisch gelöscht. Nie zum Trainieren von Modellen verwendet.',
      ),
    ).toBeInTheDocument()
    expect(within(keep).getByText('< 1 kB von 4 MB Speicher belegt')).toBeInTheDocument()
    const who = panel('Wer sie verarbeitet')
    expect(
      within(who).getByText(
        'OpenRouter leitet jede Anfrage weiter; seine eigene Verarbeitung ist nicht auf die EU ' +
          'beschränkt. Die Modelle laufen in EU-Regionen bei Microsoft Azure und Google Vertex AI.',
      ),
    ).toBeInTheDocument()
    expect(
      within(who).getByText(
        'Blockiert der Inhaltsfilter von Microsoft Azure eine Prüfung oder eine Frage an ' +
          'Klar, wird diese Anfrage (bei einer Prüfung: die Beschreibung sowie die daraus ' +
          'gewonnenen Fakten und Antworten; bei einer Frage: die Frage und, falls vorhanden, ' +
          'das Ergebnis, auf das sie sich bezieht) noch einmal an Gemini 3.1 Flash-Lite bei ' +
          'Google Vertex AI in der EU gesendet (keine Datenspeicherung beim Anbieter, kein ' +
          'Training), für jede blockierte Anfrage. Das geschieht nur, wenn der Filter sie ' +
          'blockiert.',
      ),
    ).toBeInTheDocument()
    expect(within(who).getByRole('link', { name: 'Datenschutzerklärung lesen' })).toHaveAttribute(
      'href',
      '/privacy',
    )
    const download = panel('Alles herunterladen')
    expect(
      within(download).getByRole('radio', {
        name: 'Bericht (PDF): Inventar, Ergebnisse und Pflichten',
      }),
    ).toBeChecked()
    expect(
      within(download).getByRole('radio', { name: 'Daten (JSON): alles, maschinenlesbar' }),
    ).not.toBeChecked()
    expect(within(download).getByRole('button', { name: 'Herunterladen' })).toBeInTheDocument()
  })

  it('reads the counts again after the profile is saved on Welcome', async () => {
    server.use(http.patch(INVENTORIES_URL, () => new HttpResponse(null, { status: 204 })))
    // The app keeps data fresh for 30 s: only the save's refresh makes Your data read again.
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 30_000, gcTime: Infinity } },
    })
    const user = userEvent.setup()
    const { router } = renderRoute('/app/your-data', queryClient)
    await vi.waitFor(() => expect(countOf('Company profile')).toBe('1'), {
      timeout: FIRST_RENDER_MS,
    })
    expect(store.calls.counts).toBe(1)

    await router.navigate({ to: '/app/welcome' })
    await user.click(await screen.findByRole('button', { name: '750+' }))
    await user.click(screen.getByRole('button', { name: 'Save and add a tool' }))
    await expect.poll(() => router.state.location.pathname).toBe('/app/classify')

    await router.navigate({ to: '/app/your-data' })
    await vi.waitFor(() => expect(store.calls.counts).toBe(2))
  })

  it('has no axe violations', async () => {
    const { container } = await openYourData()
    await vi.waitFor(() => expect(countOf('Classification results')).toBe('3'))
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})

const REPORT_URL = `${env.apiUrl}/reports/inventory`

describe('Your data, the report (PDF)', () => {
  let reports: unknown[]

  beforeEach(() => {
    reports = []
    server.use(
      inventoryToolsHandler(() => [
        toolRow('CV screener', WORKED_EXAMPLE),
        toolRow('Shift planner', null),
      ]),
    )
  })

  function answerWith(status: number): void {
    server.use(
      http.post(REPORT_URL, async ({ request }) => {
        reports.push(await request.json())
        if (status !== 200) return HttpResponse.json({ detail: 'refused' }, { status })
        return new HttpResponse(new Blob(['%PDF']), {
          headers: { 'Content-Type': 'application/pdf' },
        })
      }),
    )
  }

  it.each([
    ['en', 'Report (PDF): inventory, results and duties', 'Download'],
    ['de', 'Bericht (PDF): Inventar, Ergebnisse und Pflichten', 'Herunterladen'],
  ] as const)(
    'by default (%s) sends every tool, summarised, with the company, and saves the PDF',
    async (language, choice, name) => {
      answerWith(200)
      const { user } = await openYourData(language)
      expect(screen.getByRole('radio', { name: choice })).toBeChecked()
      const button = screen.getByRole('button', { name })
      await vi.waitFor(() => expect(button).toBeEnabled())
      await user.click(button)
      await vi.waitFor(() => expect(downloads).toHaveLength(1))
      expect(downloads[0]?.fileName).toBe('klar-inventory-report.pdf')
      const duties = WORKED_EXAMPLE.obligations ?? []
      expect(duties.length).toBeGreaterThan(0)
      expect(reports).toEqual([
        {
          tools: [
            {
              name: 'CV screener',
              risk_class: WORKED_EXAMPLE.risk_class,
              status: WORKED_EXAMPLE.status,
              role: WORKED_EXAMPLE.role,
              also_role: WORKED_EXAMPLE.also_role ?? null,
              law_version: WORKED_EXAMPLE.law_version,
              as_of: WORKED_EXAMPLE.as_of,
              duties: duties.map((duty) => ({
                label: language === 'de' ? duty.label_de : duty.label_en,
                article: duty.article,
                applies_from: duty.applies_from,
                legacy: duty.legacy ?? null,
              })),
            },
            { name: 'Shift planner', duties: [] },
          ],
          language,
          format: 'pdf',
          company: 'Nordwerk Logistik GmbH',
        },
      ])
    },
  )

  it.each([
    [504, 'en', 'Making this report took too long. Please try again.'],
    [504, 'de', 'Das Erstellen des Berichts hat zu lange gedauert. Bitte versuchen Sie es erneut.'],
    [500, 'en', "Klar couldn't make the report. Please try again."],
  ] as const)(
    'says why a %i made no report (%s), and sends nothing again by itself',
    async (status, language, message) => {
      answerWith(status)
      const { user } = await openYourData(language)
      const button = screen.getByRole('button', {
        name: language === 'de' ? 'Herunterladen' : 'Download',
      })
      await vi.waitFor(() => expect(button).toBeEnabled())
      await user.click(button)
      expect(await screen.findByRole('alert')).toHaveTextContent(message)
      expect(reports).toHaveLength(1)
      expect(downloads).toHaveLength(0)
    },
  )
})

describe('Your data, download and import', () => {
  it('downloads export_my_data as a dated JSON file', async () => {
    const { user } = await openYourData()
    await downloadData(user)
    await vi.waitFor(() => expect(downloads).toHaveLength(1))
    const [download] = downloads
    expect(download?.fileName).toMatch(/^klar-data-\d{4}-\d{2}-\d{2}\.json$/)
    const file: unknown = JSON.parse((await download?.blob.text()) ?? '')
    expect(file).toMatchObject({ format: 'aiact-user-data', version: 1, inventories: SAVED })
    expect(store.calls.export).toBe(1)
  })

  it('says when the download fails, and saves nothing', async () => {
    server.use(http.post(EXPORT_URL, () => HttpResponse.json({}, { status: 500 })))
    const { user } = await openYourData()
    await downloadData(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The download didn’t work. Check your connection and try again.',
    )
    expect(downloads).toHaveLength(0)
  })

  it('round-trips: a downloaded file, imported after a deletion, restores every row', async () => {
    const { user } = await openYourData()
    await vi.waitFor(() => expect(countOf('Classification results')).toBe('3'))

    await downloadData(user)
    await vi.waitFor(() => expect(downloads).toHaveLength(1))
    const text = (await downloads[0]?.blob.text()) ?? ''

    await deleteEverything(user)
    expect(await screen.findByRole('heading', { name: 'Your data is deleted.' })).toBeVisible()
    expect(store.inventories()).toEqual([])

    // A new session: Start again, then back to Your data through the sidebar.
    await user.click(screen.getByRole('link', { name: 'Start again' }))
    await screen.findByRole('heading', { level: 1, name: /where your AI tools stand/ })
    await user.click(screen.getByRole('link', { name: 'Export data' }))
    const keep = await screen.findByRole('region', { name: 'What Klar keeps' })
    await vi.waitFor(() => expect(countOf('Tools and their descriptions')).toBe('0'))

    const file = new File([text], downloads[0]?.fileName ?? 'klar-data.json', {
      type: 'application/json',
    })
    await user.upload(screen.getByLabelText('Import your data'), file)
    expect(await screen.findByText('Restored 2 tools from your file.')).toBeInTheDocument()

    expect(store.inventories()).toEqual(SAVED)
    await vi.waitFor(() => expect(countOf('Classification results')).toBe('3'))
    expect(countOf('Tools and their descriptions')).toBe('2')
    expect(countOf('Answers for your draft documents')).toBe('2')
    expect(countOf('Ticked duties on your checklists')).toBe('1')
    expect(within(keep).getByText('Company profile').nextElementSibling).toHaveTextContent('1')
  })
})

describe('Your data, delete', () => {
  it('works only once DELETE is typed exactly, and Cancel sends nothing', async () => {
    const { user } = await openYourData()
    await user.click(
      within(panel('Delete my data')).getByRole('button', { name: 'Delete my data' }),
    )
    const dialog = screen.getByRole('dialog', { name: 'Delete everything?' })
    expect(dialog).toHaveAttribute('open')
    const confirm = within(dialog).getByRole('button', { name: 'Delete everything' })
    expect(confirm).toBeDisabled()
    await user.type(within(dialog).getByLabelText('Type DELETE to confirm'), 'delete')
    expect(confirm).toBeDisabled()
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(dialog).not.toHaveAttribute('open')
    expect(store.calls.delete).toBe(0)
    expect(store.inventories()).toEqual(SAVED)
  })

  it('deletes everything, ends the session and offers to start again', async () => {
    const { user, router } = await openYourData()
    await deleteEverything(user)
    expect(await screen.findByRole('heading', { name: 'Your data is deleted.' })).toHaveFocus()
    expect(
      screen.getByText(
        'Your tools, descriptions, results, document answers, checklist ticks and company ' +
          'profile are gone, and this session has ended. Nothing is kept for training.',
      ),
    ).toBeInTheDocument()
    expect(store.calls.delete).toBe(1)
    expect(store.calls.logout).toBe(1)
    expect(store.inventories()).toEqual([])
    // The old session is signed out and forgotten; a new one starts only when the visitor goes
    // on and something needs it, so a deletion alone leaves no new anonymous user behind.
    expect(await screen.findByText('No company profile yet')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'What Klar keeps' })).toBeNull()
    expect(store.calls.signup).toBe(1)

    await user.click(screen.getByRole('link', { name: 'Start again' }))
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/app/welcome')
  })

  it('asks for LÖSCHEN in German and ends at the German confirmation', async () => {
    const { user } = await openYourData('de')
    await user.click(
      within(panel('Meine Daten löschen')).getByRole('button', { name: 'Meine Daten löschen' }),
    )
    const dialog = screen.getByRole('dialog', { name: 'Alles löschen?' })
    const field = within(dialog).getByLabelText('Geben Sie LÖSCHEN ein, um zu bestätigen')
    await user.type(field, 'DELETE')
    expect(within(dialog).getByRole('button', { name: 'Alles löschen' })).toBeDisabled()
    await user.clear(field)
    await user.type(field, 'LÖSCHEN')
    await user.click(within(dialog).getByRole('button', { name: 'Alles löschen' }))
    expect(await screen.findByRole('heading', { name: 'Ihre Daten sind gelöscht.' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Neu beginnen' })).toHaveAttribute(
      'href',
      '/app/welcome',
    )
  })

  it('states what it deletes with the counts on screen, in English and German', async () => {
    const { user, unmount } = await openYourData()
    await vi.waitFor(() => expect(countOf('Classification results')).toBe('3'))
    await openDeleteDialog(user, 'Delete my data')
    expect(
      lossText(
        'Delete everything?',
        `Klar will delete 2${NBSP}tools, 3${NBSP}results, 2${NBSP}document answers, ` +
          `1${NBSP}ticked duty and your company profile for good. This can’t be undone.`,
      ),
    ).toBeInTheDocument()
    unmount()

    const german = await openYourData('de')
    await vi.waitFor(() => expect(countOf('Ergebnisse der Einstufung')).toBe('3'))
    await openDeleteDialog(german.user, 'Meine Daten löschen')
    expect(
      lossText(
        'Alles löschen?',
        `Klar löscht 2${NBSP}Tools, 3${NBSP}Ergebnisse, 2${NBSP}Antworten für Dokumente, ` +
          `1${NBSP}abgehakte Pflicht und Ihr Unternehmensprofil endgültig. Das lässt sich nicht ` +
          'rückgängig machen.',
      ),
    ).toBeInTheDocument()
  })

  it('counts only the kinds stored, with the singular for one', async () => {
    server.use(...createUserDataStore(ONE_OF_EACH).handlers)
    const { user, unmount } = await openYourData()
    await vi.waitFor(() => expect(countOf('Classification results')).toBe('1'))
    await openDeleteDialog(user, 'Delete my data')
    expect(
      lossText(
        'Delete everything?',
        `Klar will delete 1${NBSP}tool, 1${NBSP}result, 1${NBSP}document answer and ` +
          `2${NBSP}ticked duties for good. This can’t be undone.`,
      ),
    ).toBeInTheDocument()
    unmount()

    const german = await openYourData('de')
    await vi.waitFor(() => expect(countOf('Ergebnisse der Einstufung')).toBe('1'))
    await openDeleteDialog(german.user, 'Meine Daten löschen')
    expect(
      lossText(
        'Alles löschen?',
        `Klar löscht 1${NBSP}Tool, 1${NBSP}Ergebnis, 1${NBSP}Antwort für Dokumente und ` +
          `2${NBSP}abgehakte Pflichten endgültig. Das lässt sich nicht rückgängig machen.`,
      ),
    ).toBeInTheDocument()
  })

  it('names a lone company profile within the sentence, in English and German', async () => {
    server.use(...createUserDataStore(PROFILE_ONLY).handlers)
    const { user, unmount } = await openYourData()
    await vi.waitFor(() => expect(countOf('Company profile')).toBe('1'))
    await openDeleteDialog(user, 'Delete my data')
    expect(
      lossText(
        'Delete everything?',
        'Klar will delete your company profile for good. This can’t be undone.',
      ),
    ).toBeInTheDocument()
    unmount()

    const german = await openYourData('de')
    await vi.waitFor(() => expect(countOf('Unternehmensprofil')).toBe('1'))
    await openDeleteDialog(german.user, 'Meine Daten löschen')
    expect(
      lossText(
        'Alles löschen?',
        'Klar löscht Ihr Unternehmensprofil endgültig. Das lässt sich nicht rückgängig machen.',
      ),
    ).toBeInTheDocument()
  })

  it('names the kinds instead when the counts could not be read, in English and German', async () => {
    server.use(http.post(COUNTS_URL, () => HttpResponse.json({}, { status: 500 })))
    const { user, unmount } = await openYourData()
    await screen.findByRole('alert')
    await openDeleteDialog(user, 'Delete my data')
    expect(
      within(screen.getByRole('dialog', { name: 'Delete everything?' })).getByText(
        'Your tools with their descriptions and results, your document answers, checklist ticks ' +
          'and company profile will be deleted for good. This can’t be undone.',
      ),
    ).toBeInTheDocument()
    unmount()

    const german = await openYourData('de')
    await screen.findByRole('alert')
    await openDeleteDialog(german.user, 'Meine Daten löschen')
    expect(
      within(screen.getByRole('dialog', { name: 'Alles löschen?' })).getByText(
        'Ihre Tools mit Beschreibungen und Ergebnissen, Ihre Antworten für Dokumente, abgehakten ' +
          'Pflichten und Ihr Unternehmensprofil werden endgültig gelöscht. Das lässt sich nicht ' +
          'rückgängig machen.',
      ),
    ).toBeInTheDocument()
  })

  it('keeps everything on screen and says so when the deletion fails', async () => {
    server.use(http.post(DELETE_URL, () => HttpResponse.json({}, { status: 500 })))
    const { user } = await openYourData()
    await deleteEverything(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your data wasn’t deleted. Check your connection and try again.',
    )
    expect(screen.queryByRole('heading', { name: 'Your data is deleted.' })).toBeNull()
    expect(panel('What Klar keeps')).toBeInTheDocument()
  })
})

describe('Your data, every German line', () => {
  it('shows the panels’ German copy exactly', async () => {
    await openYourData('de')
    await vi.waitFor(() => expect(countOf('Unternehmensprofil')).toBe('1'))
    for (const line of [
      'Alles liegt in Ihrer anonymen Sitzung. Nehmen Sie es mit oder löschen Sie es, wann immer Sie möchten.',
      'Antworten für Ihre Dokumententwürfe',
      'Abgehakte Pflichten in Ihren Checklisten',
      'Sprachmodelle, über OpenRouter',
      'Prüfungen und Antworten',
      'Suche in den Rechtstexten, bei einem Anbieter in der EU',
      'Embeddings',
      'Nebius macht in der EU aus Ihrer Beschreibung eine Suche in der Verordnung.',
      'Speicherung der Sitzung',
      'Ihre gespeicherten Daten, nur für Sie sichtbar.',
      'Jede Anfrage an ein Modell wird ohne Datenspeicherung beim Anbieter und ohne Training gestellt.',
      'Eine Kopie all Ihrer Daten. Der Bericht ist für Menschen; die Datendatei (JSON) für andere ' +
        'Werkzeuge. Importieren Sie die Datendatei, um sie in einer neuen Sitzung wiederherzustellen.',
      'Löscht alles, was Klar für diese Sitzung speichert: Ihre Tools, Beschreibungen, Ergebnisse, ' +
        'Antworten für Dokumente, abgehakten Pflichten und Ihr Unternehmensprofil, und beendet die ' +
        'Sitzung. Das lässt sich nicht rückgängig machen. Laden Sie vorher eine Kopie herunter, wenn ' +
        'Sie eine brauchen.',
    ]) {
      expect(screen.getByText(line)).toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: 'Abbrechen', hidden: true })).toBeInTheDocument()
  })

  it('says in German while the download is prepared, and when it fails', async () => {
    let answer: (response: Response) => void = () => undefined
    server.use(http.post(EXPORT_URL, () => new Promise<Response>((resolve) => (answer = resolve))))
    const { user } = await openYourData('de')
    await downloadData(user, 'de')
    expect(await screen.findByRole('button', { name: 'Wird vorbereitet …' })).toBeDisabled()
    answer(HttpResponse.json({}, { status: 500 }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Der Download hat nicht geklappt. Prüfen Sie Ihre Verbindung und versuchen Sie es erneut.',
    )
  })

  it('says in German while deleting, when it fails, and when it is done', async () => {
    let answer: (response: Response) => void = () => undefined
    server.use(http.post(DELETE_URL, () => new Promise<Response>((resolve) => (answer = resolve))))
    const { user } = await openYourData('de')
    await user.click(
      within(panel('Meine Daten löschen')).getByRole('button', { name: 'Meine Daten löschen' }),
    )
    await user.type(screen.getByLabelText('Geben Sie LÖSCHEN ein, um zu bestätigen'), 'LÖSCHEN')
    await user.click(screen.getByRole('button', { name: 'Alles löschen' }))
    expect(await screen.findByRole('button', { name: 'Wird gelöscht …' })).toBeDisabled()
    answer(HttpResponse.json({}, { status: 500 }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ihre Daten wurden nicht gelöscht. Prüfen Sie Ihre Verbindung und versuchen Sie es erneut.',
    )
    server.use(...store.handlers)
    await user.click(screen.getByRole('button', { name: 'Alles löschen' }))
    expect(await screen.findByRole('heading', { name: 'Ihre Daten sind gelöscht.' })).toBeVisible()
    expect(
      screen.getByText(
        'Ihre Tools, Beschreibungen, Ergebnisse, Antworten für Dokumente, abgehakten Pflichten und ' +
          'Ihr Unternehmensprofil sind gelöscht, und diese Sitzung ist beendet. Nichts wird für ' +
          'Training aufbewahrt.',
      ),
    ).toBeInTheDocument()
  })

  it('says in German when the counts cannot be read', async () => {
    server.use(http.post(COUNTS_URL, () => HttpResponse.json({}, { status: 500 })))
    await openYourData('de')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Klar konnte nicht laden, was gespeichert ist. Prüfen Sie Ihre Verbindung und laden Sie die Seite neu.',
    )
  })
})
