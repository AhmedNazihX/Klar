import { FIRST_RENDER_MS } from '@/test/timeouts'
import { onlineManager } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterAll, afterEach, describe, expect, it, vi } from 'vitest'

import { userDataOverviewKey } from '@/hooks/use-user-data-overview'
import type * as SupabaseModule from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import { reconnect } from '@/test/reconnect'
import { renderRoute } from '@/test/test-utils'
import { INVENTORIES_URL } from '@/test/user-data-handlers'
import { createUserDataStore } from '@/test/your-data-store'

import { createQueryClient } from './query-client'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

afterEach(() => {
  onlineManager.setOnline(true)
})

afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

describe('a reconnect while this tab holds its session', () => {
  it('reads the overview again after the read failed', async () => {
    const store = createUserDataStore([
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
    ])
    server.use(...store.handlers)
    // The first read of the profile fails, as on a flaky network; later reads reach the store.
    server.use(
      http.get(INVENTORIES_URL, () => HttpResponse.json({ message: 'down' }, { status: 500 }), {
        once: true,
      }),
    )
    const queryClient = createQueryClient()
    queryClient.setDefaultOptions({
      queries: { ...queryClient.getDefaultOptions().queries, retry: false },
    })
    renderRoute('/app/classify', queryClient)
    await vi.waitFor(
      () => expect(queryClient.getQueryState(userDataOverviewKey)?.status).toBe('error'),
      { timeout: FIRST_RENDER_MS },
    )
    expect(screen.queryByText('Nordwerk Logistik GmbH')).not.toBeInTheDocument()

    await reconnect(queryClient)

    expect(await screen.findByText('Nordwerk Logistik GmbH')).toBeInTheDocument()
    expect(store.calls.signup).toBe(1)
  })
})
