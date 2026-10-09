import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ClassificationResult } from '@/api'
import { env } from '@/lib/env'
import type * as SupabaseModule from '@/lib/supabase'
import { WORKED_EXAMPLE, WORKED_EXAMPLE_DESCRIPTION } from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS, inventoryRow, userDataHandlers } from '@/test/user-data-handlers'

import { putRun, type ClassificationRun } from './classification-store'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

const REPORT_URL = `${env.apiUrl}/reports/result`
const TOOL_ID = 'applicant-screening'
const COMPANY = 'Nordwerk Logistik GmbH'

let reports: unknown[]
let createObjectURL: ReturnType<typeof vi.fn>

beforeEach(() => {
  reports = []
  createObjectURL = vi.fn(() => 'blob:report')
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }))
  server.use(
    ...userDataHandlers(
      () => [inventoryRow({ company_name: COMPANY })],
      () => 1,
    ),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
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

async function openResult(
  result: ClassificationResult,
  { view, language = 'en' }: { view?: 'reviewer'; language?: 'en' | 'de' } = {},
) {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  const run: ClassificationRun = {
    toolId: TOOL_ID,
    name: 'Applicant screening',
    description: WORKED_EXAMPLE_DESCRIPTION,
    result,
  }
  putRun(client, run)
  const user = userEvent.setup()
  renderRoute(`/app/inventory/${TOOL_ID}${view ? `?view=${view}` : ''}`, client)
  await screen.findByRole(
    'heading',
    { level: 1, name: 'Applicant screening' },
    { timeout: FIRST_RENDER_MS },
  )
  // The company's name comes from its profile, read once the session exists.
  await screen.findByText(COMPANY)
  return user
}

describe('Export PDF', () => {
  it.each([
    [undefined, 'en', 'Export PDF'],
    ['reviewer', 'en', 'Export PDF'],
    [undefined, 'de', 'PDF exportieren'],
    ['reviewer', 'de', 'PDF exportieren'],
  ] as const)(
    'on the %s view in %s sends one report request with the result, the language, the tool and the company',
    async (view, language, name) => {
      answerWith(200)
      const user = await openResult(WORKED_EXAMPLE, { view, language })
      await user.click(screen.getByRole('button', { name }))
      await vi.waitFor(() => {
        expect(createObjectURL).toHaveBeenCalledTimes(1)
      })
      expect(reports).toEqual([
        {
          result: JSON.parse(JSON.stringify(WORKED_EXAMPLE)) as unknown,
          language,
          format: 'pdf',
          tool_name: 'Applicant screening',
          company: COMPANY,
        },
      ])
    },
  )

  it.each([
    [413, 'en', 'This report is too long to make into a file.'],
    [413, 'de', 'Dieser Bericht ist zu lang für eine Datei.'],
    [503, 'en', 'Klar is busy making other files. Please try again in a moment.'],
    [503, 'de', 'Klar erstellt gerade andere Dateien. Bitte versuchen Sie es gleich noch einmal.'],
    [504, 'en', 'Making this report took too long. Please try again.'],
    [504, 'de', 'Das Erstellen des Berichts hat zu lange gedauert. Bitte versuchen Sie es erneut.'],
    [422, 'en', "Klar couldn't make the report. Please try again."],
    [422, 'de', 'Klar konnte den Bericht nicht erstellen. Bitte versuchen Sie es erneut.'],
  ] as const)(
    'says why a %i made no report (%s), and sends nothing again by itself',
    async (status, language, message) => {
      answerWith(status)
      const user = await openResult(WORKED_EXAMPLE, { language })
      const name = language === 'de' ? 'PDF exportieren' : 'Export PDF'
      await user.click(screen.getByRole('button', { name }))
      expect(await screen.findByRole('alert')).toHaveTextContent(message)
      expect(reports).toHaveLength(1)
      expect(createObjectURL).not.toHaveBeenCalled()
    },
  )

  it.each([
    ['en', 'Export PDF', 'Making the PDF…'],
    ['de', 'PDF exportieren', 'PDF wird erstellt …'],
  ] as const)(
    'says the PDF is being made (%s) and takes no second click meanwhile',
    async (language, name, pending) => {
      server.use(
        http.post(REPORT_URL, async ({ request }) => {
          reports.push(await request.json())
          return new Promise<Response>(() => undefined)
        }),
      )
      const user = await openResult(WORKED_EXAMPLE, { language })
      await user.click(screen.getByRole('button', { name }))
      const button = await screen.findByRole('button', { name: pending })
      expect(button).toBeDisabled()
      await user.click(button)
      expect(reports).toHaveLength(1)
    },
  )
})
