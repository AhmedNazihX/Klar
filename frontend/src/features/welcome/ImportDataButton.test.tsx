import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import {
  FIRST_RENDER_MS,
  IMPORT_URL,
  inventoryRow,
  userDataHandlers,
} from '@/test/user-data-handlers'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

// A file as Your data exports it (export_my_data, format version 1), trimmed to one tool.
const EXPORT = {
  format: 'aiact-user-data',
  version: 1,
  exported_at: '2026-10-01T09:00:00+00:00',
  inventories: [
    {
      name: 'AI inventory',
      company_name: 'Nordwerk Logistik GmbH',
      staff_band: '10-49',
      turnover_band: 'up_to_10m',
      established_in: 'DE',
      used_in: 'eu',
      created_at: '2026-09-30T09:00:00+00:00',
      systems: [{ name: 'CV screener', description: 'Ranks applicants.', classifications: [] }],
    },
  ],
}

let rows: Record<string, unknown>[] = []
let toolCount = 0

beforeEach(() => {
  rows = []
  toolCount = 0
  server.use(
    ...userDataHandlers(
      () => rows,
      () => toolCount,
    ),
  )
})
afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

async function openWelcome() {
  const user = userEvent.setup()
  renderRoute('/app/welcome')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
  return user
}

function exportFile(text: string): File {
  return new File([text], 'klar-data.json', { type: 'application/json' })
}

describe('Import your data', () => {
  it('restores an exported file through import_my_data', async () => {
    let sent: unknown = null
    server.use(
      http.post(IMPORT_URL, async ({ request }) => {
        sent = await request.json()
        rows = [inventoryRow({ company_name: 'Nordwerk Logistik GmbH', staff_band: '10-49' })]
        toolCount = 1
        return HttpResponse.json({ inventories: 1, systems: 1, classifications: 0 })
      }),
    )
    const user = await openWelcome()
    await user.upload(screen.getByLabelText('Import your data'), exportFile(JSON.stringify(EXPORT)))

    expect(await screen.findByText('Restored 1 tool from your file.')).toHaveAttribute(
      'role',
      'status',
    )
    expect(sent).toEqual({ data: EXPORT })
    const tools = screen.getByRole('region', { name: 'Your AI tools' })
    expect(await within(tools).findByText('Your inventory holds 1 tool.')).toBeInTheDocument()
    expect(screen.getByLabelText('Company name')).toHaveValue('Nordwerk Logistik GmbH')
  })

  it('refuses a file that is not JSON without sending it', async () => {
    let calls = 0
    server.use(
      http.post(IMPORT_URL, () => {
        calls += 1
        return HttpResponse.json({ inventories: 0, systems: 0 })
      }),
    )
    const user = await openWelcome()
    await user.upload(screen.getByLabelText('Import your data'), exportFile('not json'))
    expect(await screen.findByRole('alert')).toHaveTextContent("This file isn't a Klar export.")
    expect(calls).toBe(0)
  })

  it('says when the server refuses the file as not an export', async () => {
    server.use(
      http.post(IMPORT_URL, () =>
        HttpResponse.json(
          { code: '22023', message: 'not an export', details: null, hint: null },
          { status: 400 },
        ),
      ),
    )
    const user = await openWelcome()
    await user.upload(screen.getByLabelText('Import your data'), exportFile('{"format":"other"}'))
    expect(await screen.findByRole('alert')).toHaveTextContent("This file isn't a Klar export.")
  })
})
