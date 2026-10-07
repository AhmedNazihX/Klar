import type { SupabaseClient } from '@supabase/supabase-js'
import { screen } from '@testing-library/react'
import { afterAll, afterEach, describe, expect, it, vi } from 'vitest'

import { readDraft, saveDraft } from '@/features/classify/classification-store'
import { EMPTY_OVERVIEW } from '@/lib/company-profile'
import type * as SupabaseModule from '@/lib/supabase'
import { createSupabase, supabase } from '@/lib/supabase'
import { SUPABASE_URL } from '@/test/supabase-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

import { userDataOverviewKey } from './use-user-data-overview'

vi.mock('@/lib/supabase', async (importOriginal) => {
  const actual = await importOriginal<typeof SupabaseModule>()
  const { SUPABASE_URL } = await import('@/test/supabase-fixtures')
  return {
    ...actual,
    supabase: actual.createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' }),
  }
})

const COUNTS_KEY = ['user-data', 'counts']
const RUN_KEY = ['classification-run', 'tool-1']
const SESSION_KEY = ['auth', 'anonymous-session']

let otherTab: SupabaseClient | null = null

afterEach(async () => {
  await otherTab?.auth.stopAutoRefresh()
  otherTab = null
})

afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

describe('a sign-out in another tab', () => {
  it('forgets the draft and the cached user data, runs and session in this one', async () => {
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(userDataOverviewKey, {
      inventoryId: 'inventory-1',
      profile: null,
      toolCount: 2,
    })
    queryClient.setQueryData(COUNTS_KEY, { systems: 2 })
    queryClient.setQueryData(RUN_KEY, { toolId: 'tool-1' })
    queryClient.setQueryData(SESSION_KEY, 'user-1')
    saveDraft({ name: 'CV screener', description: 'Ranks applicants.' })
    renderRoute('/privacy', queryClient)
    await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })

    // Another tab's client, on the same stored session, ends it (as Delete my data does there):
    // supabase-js tells this tab's client of the SIGNED_OUT.
    otherTab = createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' })
    const signedOut = await otherTab?.auth.signOut()
    expect(signedOut?.error).toBeNull()

    await vi.waitFor(() => expect(readDraft()).toEqual({ name: '', description: '' }))
    expect(queryClient.getQueryData(COUNTS_KEY)).toBeUndefined()
    expect(queryClient.getQueryData(RUN_KEY)).toBeUndefined()
    expect(queryClient.getQueryData(SESSION_KEY)).toBeUndefined()
    expect(queryClient.getQueryData(userDataOverviewKey)).toEqual(EMPTY_OVERVIEW)
  })
})
