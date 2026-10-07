import type { SupabaseClient } from '@supabase/supabase-js'
import { QueryObserver } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createSupabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import { reconnect } from '@/test/reconnect'
import { anonymousSession, SIGNUP_URL, SUPABASE_URL, USER_ID } from '@/test/supabase-fixtures'
import { createTestQueryClient } from '@/test/test-utils'

import { anonymousSessionOptions, endAnonymousSession } from './use-anonymous-session'

const SESSION_KEY = ['auth', 'anonymous-session']

let tabs: SupabaseClient[] = []

/** A tab's client: each has its own query client and supabase-js, all on one localStorage. */
function openTab(): SupabaseClient {
  const client = createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' })
  if (!client) throw new Error('expected a client')
  tabs = [...tabs, client]
  return client
}

/** A tab's first use of the session: its own query client asks for the user id. */
function startSession(client: SupabaseClient): Promise<string> {
  return createTestQueryClient().query(anonymousSessionOptions(client))
}

/** Counts anonymous sign-ins; each one makes a new anonymous user. */
function countSignups(): { count: () => number } {
  let signups = 0
  server.use(
    http.post(SIGNUP_URL, () => {
      signups += 1
      return HttpResponse.json(anonymousSession())
    }),
  )
  return { count: () => signups }
}

/**
 * Web Locks for jsdom, which has none, as the browser grants them: one holder per name at a time,
 * in the order asked. Records the names asked for.
 */
function installLocks(): { names: string[] } {
  const names: string[] = []
  let released: Promise<void> = Promise.resolve()
  async function request<T>(name: string, callback: LockGrantedCallback<T>): Promise<Awaited<T>> {
    names.push(name)
    const previousReleased = released
    let release: () => void = () => undefined
    released = new Promise((resolve) => {
      release = resolve
    })
    await previousReleased
    try {
      return await callback({ name, mode: 'exclusive' })
    } finally {
      release()
    }
  }
  const locks = { request, query: () => Promise.resolve({ held: [], pending: [] }) }
  Object.defineProperty(navigator, 'locks', { value: locks, configurable: true })
  return { names }
}

afterEach(async () => {
  Reflect.deleteProperty(navigator, 'locks')
  await Promise.all(tabs.map((client) => client.auth.stopAutoRefresh()))
  tabs = []
})

describe('an ended session', () => {
  it('is not started again by the network coming back, even where reconnects refetch', async () => {
    const signups = countSignups()
    // The test client keeps TanStack's default of refetching stale queries on reconnect.
    const queryClient = createTestQueryClient()
    queryClient.mount()
    const session = new QueryObserver(queryClient, anonymousSessionOptions(openTab()))
    const stopObserving = session.subscribe(() => undefined)
    await vi.waitFor(() => expect(session.getCurrentResult().data).toBe(USER_ID))

    endAnonymousSession(queryClient)
    await reconnect(queryClient)

    // Not fetched again: still the one sign-in's data, still marked as ended.
    expect(queryClient.getQueryState(SESSION_KEY)).toMatchObject({
      isInvalidated: true,
      dataUpdateCount: 1,
    })
    expect(signups.count()).toBe(1)
    stopObserving()
    queryClient.unmount()
  })
})

describe('two tabs using the session for the first time at once', () => {
  it('make one anonymous user: the second waits for the lock, then reuses the stored session', async () => {
    const signups = countSignups()
    const locks = installLocks()

    const ids = await Promise.all([startSession(openTab()), startSession(openTab())])

    expect(ids).toEqual([USER_ID, USER_ID])
    expect(signups.count()).toBe(1)
    expect(locks.names).toEqual(['klar.anonymous-session', 'klar.anonymous-session'])
  })

  it('each sign in where the browser has no Web Locks, as before the lock', async () => {
    const signups = countSignups()
    expect('locks' in navigator).toBe(false)

    const ids = await Promise.all([startSession(openTab()), startSession(openTab())])

    expect(ids).toEqual([USER_ID, USER_ID])
    expect(signups.count()).toBe(2)
  })
})
