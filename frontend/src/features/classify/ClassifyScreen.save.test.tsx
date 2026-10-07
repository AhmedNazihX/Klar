// Classify with Supabase configured (P6): a finished run becomes a tool in the inventory. The
// other Classify tests run without Supabase, where nothing is saved.
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import {
  classifyHandler,
  WORKED_EXAMPLE,
  WORKED_EXAMPLE_DESCRIPTION,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { CLASSIFICATIONS_URL } from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import {
  FIRST_RENDER_MS,
  INVENTORIES_URL,
  INVENTORY_ID,
  inventoryRow,
  SYSTEMS_URL,
  userDataHandlers,
} from '@/test/user-data-handlers'

import { clearDraft } from './classification-store'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

const SYSTEM_ID = '3b9d2f1e-6a4c-4e0b-8f3a-1c2d3e4f5a6b'

let inventories: Record<string, unknown>[] = []
let writes: { table: string; body: unknown }[] = []
let classifyRequests = 0

/** Records the writes a save makes; the run's insert fails with `runError` when given. */
function saveHandlers(runError: { status: number; code: string } | null = null) {
  return [
    http.post(INVENTORIES_URL, async ({ request }) => {
      writes.push({ table: 'inventories', body: await request.json() })
      return HttpResponse.json({ id: INVENTORY_ID }, { status: 201 })
    }),
    http.post(SYSTEMS_URL, async ({ request }) => {
      writes.push({ table: 'systems', body: await request.json() })
      return HttpResponse.json({ id: SYSTEM_ID }, { status: 201 })
    }),
    http.post(CLASSIFICATIONS_URL, async ({ request }) => {
      writes.push({ table: 'classifications', body: await request.json() })
      return runError
        ? HttpResponse.json(
            { code: runError.code, message: 'refused' },
            { status: runError.status },
          )
        : new HttpResponse(null, { status: 201 })
    }),
    http.delete(SYSTEMS_URL, () => new HttpResponse(null, { status: 204 })),
  ]
}

beforeEach(() => {
  clearDraft()
  inventories = [inventoryRow()]
  writes = []
  classifyRequests = 0
  server.use(
    ...userDataHandlers(
      () => inventories,
      () => 0,
    ),
    classifyHandler(WORKED_EXAMPLE_EVENTS, () => {
      classifyRequests += 1
    }),
  )
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

async function classify(name: string, language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const user = userEvent.setup()
  const rendered = renderRoute('/app/classify')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
  const labels =
    language === 'de'
      ? { name: 'Wie nennen Sie das Tool?', description: 'In Ihren eigenen Worten' }
      : { name: 'What do you call the tool?', description: 'In your own words' }
  if (name) await user.type(screen.getByLabelText(labels.name), name)
  await user.type(screen.getByLabelText(labels.description), WORKED_EXAMPLE_DESCRIPTION)
  await user.click(
    screen.getByRole('button', {
      name: language === 'de' ? 'Prüfungen starten' : 'Run the checks',
    }),
  )
  return rendered
}

describe('Classify, saving the run to the inventory', () => {
  it('adds the tool and its run to the inventory and opens the saved tool', async () => {
    server.use(...saveHandlers())
    const { router } = await classify('Applicant screening')

    await expect.poll(() => router.state.location.pathname).toBe(`/app/inventory/${SYSTEM_ID}`)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Applicant screening' }),
    ).toBeInTheDocument()
    expect(writes).toEqual([
      {
        table: 'systems',
        body: {
          inventory_id: INVENTORY_ID,
          name: 'Applicant screening',
          description: WORKED_EXAMPLE_DESCRIPTION,
        },
      },
      {
        table: 'classifications',
        body: {
          system_id: SYSTEM_ID,
          risk_class: WORKED_EXAMPLE.risk_class,
          status: WORKED_EXAMPLE.status,
          law_version: WORKED_EXAMPLE.law_version,
          result: WORKED_EXAMPLE,
          inputs: { description: WORKED_EXAMPLE_DESCRIPTION, answers: {} },
        },
      },
    ])
    expect(screen.queryByRole('alert')).toBeNull()
    expect(classifyRequests).toBe(1)
  })

  it.each([
    ['en', 'AI inventory', 'Your tool'],
    ['de', 'KI-Inventar', 'Ihr Tool'],
  ] as const)(
    'creates the inventory when there is none, and names an unnamed tool (%s)',
    async (language, inventoryName, toolName) => {
      inventories = []
      server.use(...saveHandlers())
      await classify('', language)

      await expect.poll(() => writes.length).toBe(3)
      expect(writes[0]).toEqual({ table: 'inventories', body: { name: inventoryName } })
      expect(writes[1]?.body).toMatchObject({ inventory_id: INVENTORY_ID, name: toolName })
    },
  )

  it.each([
    [
      'en',
      'PT507',
      "This result wasn't saved: your data has reached its storage limit. Make room under Your data, then run the checks again.",
    ],
    [
      'de',
      'PT507',
      'Dieses Ergebnis wurde nicht gespeichert: Ihre Daten haben die Speichergrenze erreicht. Schaffen Sie unter „Ihre Daten“ Platz und starten Sie die Prüfungen erneut.',
    ],
    [
      'en',
      'XX000',
      "This result wasn't saved to your inventory. It stays on this page until you reload or leave it.",
    ],
    [
      'de',
      'XX000',
      'Dieses Ergebnis wurde nicht in Ihrem Inventar gespeichert. Es bleibt auf dieser Seite, bis Sie sie neu laden oder verlassen.',
    ],
  ] as const)(
    'still opens a run it could not save, and says so (%s, %s)',
    async (language, code, message) => {
      server.use(...saveHandlers({ status: 400, code }))
      const { router } = await classify('Applicant screening', language)

      expect(await screen.findByRole('alert', {}, { timeout: FIRST_RENDER_MS })).toHaveTextContent(
        message,
      )
      expect(router.state.location.pathname).toMatch(/^\/app\/inventory\/[\w-]+$/)
      expect(router.state.location.pathname).not.toBe(`/app/inventory/${SYSTEM_ID}`)
      expect(screen.getByRole('heading', { level: 1, name: 'Applicant screening' })).toBeVisible()
      // Nothing is run again: the run was paid for once.
      expect(classifyRequests).toBe(1)
    },
  )
})
