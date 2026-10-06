import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import {
  FIRST_RENDER_MS,
  INVENTORIES_URL,
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

async function start(path = '/app'): Promise<string> {
  const { router } = renderRoute(path)
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
  return router.state.location.pathname
}

describe('the app start', () => {
  it('sends a first visit (no profile, no tool) to Welcome', async () => {
    rows = [inventoryRow()]
    expect(await start()).toBe('/app/welcome')
  })

  it('opens the inventory once a profile exists', async () => {
    rows = [inventoryRow({ company_name: 'Nordwerk Logistik GmbH' })]
    expect(await start()).toBe('/app/inventory')
  })

  it('opens the inventory once a tool exists', async () => {
    toolCount = 2
    expect(await start()).toBe('/app/inventory')
  })

  it('opens the inventory when the data cannot be read', async () => {
    server.use(
      http.get(INVENTORIES_URL, () => HttpResponse.json({ message: 'down' }, { status: 500 })),
    )
    expect(await start()).toBe('/app/inventory')
  })
})

describe('the sidebar company line', () => {
  it('shows the company name, staff band and size class from the profile', async () => {
    rows = [
      inventoryRow({
        company_name: 'Nordwerk Logistik GmbH',
        staff_band: '10-49',
        turnover_band: 'up_to_10m',
        size_class: 'sme',
      }),
    ]
    await start()
    const line = await screen.findByRole('link', { name: /Nordwerk Logistik GmbH/ })
    expect(line).toHaveTextContent('10–49 staff, counts as an SME')
    expect(line).toHaveAttribute('href', '/app/welcome')
  })

  it('names no small mid-cap under the original 2024 text', async () => {
    const profile = { company_name: 'Acme', staff_band: '250-749', turnover_band: 'up_to_50m' }
    rows = [inventoryRow({ ...profile, size_class: 'smc' })]
    await start('/app?law=original')
    const line = await screen.findByRole('link', { name: /Acme/ })
    expect(line).toHaveTextContent('250–749 staff')
    expect(line).not.toHaveTextContent('small mid-cap')
  })

  it('names the small mid-cap under the amended text', async () => {
    const profile = { company_name: 'Acme', staff_band: '250-749', turnover_band: 'up_to_50m' }
    rows = [inventoryRow({ ...profile, size_class: 'smc' })]
    await start()
    const line = await screen.findByRole('link', { name: /Acme/ })
    expect(line).toHaveTextContent('250–749 staff, counts as a small mid-cap')
  })

  it('says there is no profile yet without one', async () => {
    await start()
    expect(screen.getByRole('link', { name: /No company profile yet/ })).toBeInTheDocument()
  })
})
