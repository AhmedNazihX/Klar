import { FIRST_RENDER_MS } from '@/test/timeouts'
import type { SupabaseClient } from '@supabase/supabase-js'
import { onlineManager } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterAll, afterEach, describe, expect, it, vi } from 'vitest'

import { readDraft, saveDraft, toolResultKey } from '@/features/classify/classification-store'
import { EMPTY_OVERVIEW } from '@/lib/company-profile'
import { createQueryClient } from '@/lib/query-client'
import type * as SupabaseModule from '@/lib/supabase'
import { createSupabase, supabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import { reconnect } from '@/test/reconnect'
import { anonymousSession, SIGNUP_URL, SUPABASE_URL, USER_ID } from '@/test/supabase-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { INVENTORIES_URL, SYSTEMS_URL } from '@/test/user-data-handlers'
import { createUserDataStore, type StoredInventory } from '@/test/your-data-store'

import { withAnonymousSession } from './use-anonymous-session'
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
const RUN_KEY = toolResultKey('tool-1')
const SESSION_KEY = ['auth', 'anonymous-session']

// A company profile and no tools: the sidebar names the company until the session is forgotten.
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

let otherTab: SupabaseClient | null = null

/** A second tab's client on the same stored session, as another open tab of the app has. */
function openOtherTab(): SupabaseClient {
  otherTab = createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' })
  if (!otherTab) throw new Error('expected a client')
  return otherTab
}

afterEach(async () => {
  onlineManager.setOnline(true)
  server.events.removeAllListeners()
  await otherTab?.auth.stopAutoRefresh()
  otherTab = null
})

afterAll(async () => {
  await supabase?.auth.stopAutoRefresh()
})

describe('a sign-out in another tab', () => {
  it('forgets this tab’s draft, user data and runs, and signs in again only when used', async () => {
    const store = createUserDataStore(PROFILE_ONLY)
    server.use(...store.handlers)
    const queryClient = createTestQueryClient()
    queryClient.setQueryData(COUNTS_KEY, { systems: 2 })
    queryClient.setQueryData(RUN_KEY, { toolId: 'tool-1' })
    // A draft for a tool the user has ("Classify this tool"): the tool is forgotten with it.
    saveDraft(
      { name: 'CV screener', description: 'Ranks applicants.' },
      { toolId: 'tool-1', name: 'CV screener' },
    )
    renderRoute('/app/classify', queryClient)
    // The app frame starts this tab's session and shows the profile it reads.
    expect(await screen.findByText('Nordwerk Logistik GmbH')).toBeInTheDocument()
    expect(store.calls.signup).toBe(1)

    // Another tab ends the session (as Delete my data does there): supabase-js tells this one.
    const signedOut = await openOtherTab().auth.signOut()
    expect(signedOut.error).toBeNull()

    await vi.waitFor(() =>
      expect(readDraft()).toEqual({ values: { name: '', description: '' }, tool: null }),
    )
    expect(queryClient.getQueryData(COUNTS_KEY)).toBeUndefined()
    expect(queryClient.getQueryData(RUN_KEY)).toBeUndefined()
    expect(queryClient.getQueryData(userDataOverviewKey)).toEqual(EMPTY_OVERVIEW)
    expect(await screen.findByText('No company profile yet')).toBeInTheDocument()
    // The session is marked as ended, not started again: this tab hasn't been used since.
    expect(queryClient.getQueryState(SESSION_KEY)).toMatchObject({
      isInvalidated: true,
      fetchStatus: 'idle',
    })
    expect(store.calls.signup).toBe(1)

    // The other tab goes on first and starts the one new session; this tab, used next, takes
    // that stored session instead of signing in a second time.
    const signedIn = await otherTab?.auth.signInAnonymously()
    expect(signedIn?.error).toBeNull()
    expect(store.calls.signup).toBe(2)
    await withAnonymousSession(queryClient, supabase)
    expect(queryClient.getQueryState(SESSION_KEY)).toMatchObject({
      data: USER_ID,
      isInvalidated: false,
    })
    expect(store.calls.signup).toBe(2)
  })

  it('signs in on this tab’s next use when no other tab has', async () => {
    const store = createUserDataStore(PROFILE_ONLY)
    server.use(...store.handlers)
    const queryClient = createTestQueryClient()
    renderRoute('/app/classify', queryClient)
    await screen.findByText('Nordwerk Logistik GmbH')

    await openOtherTab().auth.signOut()
    expect(await screen.findByText('No company profile yet')).toBeInTheDocument()
    expect(store.calls.signup).toBe(1)

    await withAnonymousSession(queryClient, supabase)
    expect(store.calls.signup).toBe(2)
  })
})

describe('a sign-out while this tab’s session is still starting', () => {
  it('keeps the session loading and the draft, and signs in once', async () => {
    // At start-up supabase-js signs out a stored session that is no longer valid, while the
    // session's query is already waiting on the sign-in.
    let signups = 0
    let answerSignup: () => void = () => undefined
    const signupAnswered = new Promise<void>((resolve) => {
      answerSignup = resolve
    })
    server.use(...createUserDataStore(PROFILE_ONLY).handlers)
    // Ahead of the store's own sign-up: this one answers only when the test says so.
    server.use(
      http.post(SIGNUP_URL, async () => {
        signups += 1
        await signupAnswered
        return HttpResponse.json(anonymousSession())
      }),
    )
    let stopListening: () => void = () => undefined
    const heardSignOut = new Promise<void>((resolve) => {
      const listener = supabase?.auth.onAuthStateChange((event) => {
        if (event === 'SIGNED_OUT') resolve()
      })
      stopListening = () => listener?.data.subscription.unsubscribe()
    })
    const queryClient = createTestQueryClient()
    renderRoute('/app/classify', queryClient)
    await expect.poll(() => signups, { timeout: FIRST_RENDER_MS }).toBe(1)
    // Typed while the session starts: this tab holds no session yet, so nothing is forgotten.
    saveDraft({ name: 'CV screener', description: 'Ranks applicants.' })

    await openOtherTab().auth.signOut()
    await heardSignOut
    stopListening()
    expect(queryClient.getQueryState(SESSION_KEY)).toMatchObject({
      status: 'pending',
      fetchStatus: 'fetching',
    })
    expect(readDraft()).toEqual({
      values: { name: 'CV screener', description: 'Ranks applicants.' },
      tool: null,
    })

    answerSignup()
    await vi.waitFor(() => expect(queryClient.getQueryData(SESSION_KEY)).toBe(USER_ID))
    expect(await screen.findByText('Nordwerk Logistik GmbH')).toBeInTheDocument()
    expect(signups).toBe(1)
  })
})

describe('after a sign-out in another tab', () => {
  it('starts no session when the network comes back', async () => {
    const store = createUserDataStore(PROFILE_ONLY)
    server.use(...store.handlers)
    // The app's own query client, with every read stale at once: a reconnect would refetch the
    // sidebar's overview, if the app let it, and that read would sign in.
    const queryClient = createQueryClient()
    queryClient.setDefaultOptions({
      queries: { ...queryClient.getDefaultOptions().queries, staleTime: 0, retry: false },
    })
    renderRoute('/app/classify', queryClient)
    await screen.findByText('Nordwerk Logistik GmbH')
    await openOtherTab().auth.signOut()
    expect(await screen.findByText('No company profile yet')).toBeInTheDocument()

    await reconnect(queryClient)

    expect(queryClient.getQueryState(SESSION_KEY)).toMatchObject({ isInvalidated: true })
    expect(store.calls.signup).toBe(1)
  })

  it('drops a read of the overview that was under way, so the old profile stays gone', async () => {
    const store = createUserDataStore(PROFILE_ONLY)
    server.use(...store.handlers)
    const queryClient = createTestQueryClient()
    renderRoute('/app/classify', queryClient)
    await screen.findByText('Nordwerk Logistik GmbH')

    // The next read of the profile waits until the test lets it through, then gets the store's
    // answer, which still holds the profile (only the session has ended).
    let heldReads = 0
    let release: () => void = () => undefined
    const released = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.get(INVENTORIES_URL, async () => {
        heldReads += 1
        await released
        return undefined
      }),
    )
    // The read's last request is the tool count.
    const answered = new Promise<void>((resolve) => {
      server.events.on('response:mocked', ({ request }) => {
        if (request.method === 'HEAD' && request.url.startsWith(SYSTEMS_URL)) resolve()
      })
    })
    const heldRead = queryClient.refetchQueries({ queryKey: userDataOverviewKey, exact: true })
    await expect.poll(() => heldReads).toBe(1)

    await openOtherTab().auth.signOut()
    expect(await screen.findByText('No company profile yet')).toBeInTheDocument()

    release()
    await answered
    await heldRead
    expect(queryClient.getQueryData(userDataOverviewKey)).toEqual(EMPTY_OVERVIEW)
    expect(screen.queryByText('Nordwerk Logistik GmbH')).not.toBeInTheDocument()
    expect(store.calls.signup).toBe(1)
  })
})
