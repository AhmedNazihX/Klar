import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'
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

/** The count shown beside a row's label in "What Klar keeps". */
function countOf(label: string): string | null {
  return screen.getByText(label).nextElementSibling?.textContent ?? null
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
    expect(within(keep).getByText(/^\d+ kB of 4 MB storage used$/)).toBeInTheDocument()
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
    expect(within(keep).getByText(/^\d+ kB von 4 MB Speicher belegt$/)).toBeInTheDocument()
    const who = panel('Wer sie verarbeitet')
    expect(
      within(who).getByText(
        'OpenRouter leitet jede Anfrage weiter; seine eigene Verarbeitung ist nicht auf die EU ' +
          'beschränkt. Die Modelle laufen in EU-Regionen bei Microsoft Azure und Google Vertex AI.',
      ),
    ).toBeInTheDocument()
    expect(within(who).getByRole('link', { name: 'Datenschutzerklärung lesen' })).toHaveAttribute(
      'href',
      '/privacy',
    )
    expect(
      within(panel('Alles herunterladen')).getByRole('button', {
        name: 'Daten herunterladen (JSON)',
      }),
    ).toBeInTheDocument()
  })

  it('has no axe violations', async () => {
    const { container } = await openYourData()
    await vi.waitFor(() => expect(countOf('Classification results')).toBe('3'))
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})

describe('Your data, download and import', () => {
  it('downloads export_my_data as a dated JSON file', async () => {
    const { user } = await openYourData()
    await user.click(screen.getByRole('button', { name: 'Download data (JSON)' }))
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
    await user.click(screen.getByRole('button', { name: 'Download data (JSON)' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The download didn’t work. Check your connection and try again.',
    )
    expect(downloads).toHaveLength(0)
  })

  it('round-trips: a downloaded file, imported after a deletion, restores every row', async () => {
    const { user } = await openYourData()
    await vi.waitFor(() => expect(countOf('Classification results')).toBe('3'))

    await user.click(screen.getByRole('button', { name: 'Download data (JSON)' }))
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
    // The old session is signed out; the app frame starts a fresh, empty one.
    await vi.waitFor(() => expect(store.calls.signup).toBe(2))
    expect(screen.queryByRole('region', { name: 'What Klar keeps' })).toBeNull()
    expect(screen.getByText('No company profile yet')).toBeInTheDocument()

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
    expect(
      within(dialog).getByText(
        'Ihre Tools mit Beschreibungen und Ergebnissen, Ihre Antworten für Dokumente, abgehakten ' +
          'Pflichten und Ihr Unternehmensprofil werden endgültig gelöscht. Klar kann sie nicht ' +
          'wiederherstellen.',
      ),
    ).toBeInTheDocument()
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
      'Eine Kopie all Ihrer Daten in einer Datei (JSON), für Ihre Unterlagen oder andere Werkzeuge. ' +
        'Importieren Sie sie, um sie in einer neuen Sitzung wiederherzustellen.',
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
    await user.click(screen.getByRole('button', { name: 'Daten herunterladen (JSON)' }))
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
