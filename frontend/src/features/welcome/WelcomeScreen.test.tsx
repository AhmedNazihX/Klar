import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import { renderRoute } from '@/test/test-utils'
import {
  INVENTORIES_URL,
  INVENTORY_ID,
  inventoryRow,
  userDataHandlers,
} from '@/test/user-data-handlers'

// The app's Supabase client, pointed at the MSW network boundary.
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

async function openWelcome() {
  const user = userEvent.setup()
  const rendered = renderRoute('/app/welcome')
  await screen.findByRole('heading', { level: 1, name: "Let's see where your AI tools stand." })
  return { user, ...rendered }
}

describe('Welcome, saving the profile', () => {
  it('inserts the profile on a new inventory and goes on to Classify', async () => {
    let inserted: unknown = null
    server.use(
      http.post(INVENTORIES_URL, async ({ request }) => {
        inserted = await request.json()
        return new HttpResponse(null, { status: 201 })
      }),
    )
    const { user, router } = await openWelcome()
    await user.type(screen.getByLabelText('Company name'), 'Nordwerk Logistik GmbH')
    await user.click(screen.getByRole('button', { name: '10–49' }))
    await user.click(screen.getByRole('button', { name: 'Up to €10 m' }))
    await user.selectOptions(screen.getByLabelText('Where you are established'), 'DE')
    await user.click(screen.getByRole('button', { name: 'In the EU' }))
    await user.click(screen.getByRole('button', { name: 'Save and add a tool' }))

    await expect.poll(() => router.state.location.pathname).toBe('/app/classify')
    expect(inserted).toEqual({
      name: 'AI inventory',
      company_name: 'Nordwerk Logistik GmbH',
      staff_band: '10-49',
      turnover_band: 'up_to_10m',
      established_in: 'DE',
      used_in: 'eu',
    })
  })

  it('updates the existing inventory, with unset fields as null', async () => {
    rows = [inventoryRow()]
    let patchedId: string | null = null
    let patchedBody: unknown = null
    server.use(
      http.patch(INVENTORIES_URL, async ({ request }) => {
        patchedId = new URL(request.url).searchParams.get('id')
        patchedBody = await request.json()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user, router } = await openWelcome()
    await user.click(screen.getByRole('button', { name: '750+' }))
    await user.click(screen.getByRole('button', { name: 'Save and add a tool' }))

    await expect.poll(() => router.state.location.pathname).toBe('/app/classify')
    expect(patchedId).toBe(`eq.${INVENTORY_ID}`)
    expect(patchedBody).toEqual({
      company_name: null,
      staff_band: '750+',
      turnover_band: null,
      established_in: null,
      used_in: null,
    })
  })

  it('skips to Classify without writing anything', async () => {
    let writes = 0
    server.use(
      http.post(INVENTORIES_URL, () => {
        writes += 1
        return new HttpResponse(null, { status: 201 })
      }),
    )
    const { user, router } = await openWelcome()
    await user.click(screen.getByRole('button', { name: 'Skip for now' }))
    await expect.poll(() => router.state.location.pathname).toBe('/app/classify')
    expect(writes).toBe(0)
  })

  it('shows a full storage with its hint, apart from other errors', async () => {
    server.use(
      http.post(INVENTORIES_URL, () =>
        HttpResponse.json(
          { code: 'PT507', message: 'storage full: server detail', details: null, hint: 'x' },
          { status: 507 },
        ),
      ),
    )
    const { user, router } = await openWelcome()
    await user.click(screen.getByRole('button', { name: 'Save and add a tool' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Your saved data is full')
    expect(within(alert).getByRole('link', { name: 'Go to Your data' })).toHaveAttribute(
      'href',
      '/app/your-data',
    )
    expect(alert).not.toHaveTextContent('server detail')
    expect(router.state.location.pathname).toBe('/app/welcome')
  })
})
