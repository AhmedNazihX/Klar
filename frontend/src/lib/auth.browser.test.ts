import type { SupabaseClient } from '@supabase/supabase-js'
import { describe, expect, it } from 'vitest'

import { ensureAnonymousSession } from './auth'

/**
 * Two tabs' auth clients on one stored session, as supabase-js keeps it in localStorage. This
 * project has no network (no MSW), so the clients are stand-ins; the Web Locks are Chromium's own.
 * Each sign-in takes a moment, as a real one does, and makes a new user.
 */
function twoTabs(): { tabs: [SupabaseClient, SupabaseClient]; signups: () => number } {
  let storedUserId: string | null = null
  let signups = 0
  const tab = {
    auth: {
      getSession: () =>
        Promise.resolve({
          data: { session: storedUserId ? { user: { id: storedUserId } } : null },
          error: null,
        }),
      signInAnonymously: async () => {
        signups += 1
        const userId = `user-${String(signups)}`
        await new Promise((resolve) => requestAnimationFrame(resolve))
        storedUserId = userId
        return { data: { user: { id: userId } }, error: null }
      },
    },
  } as unknown as SupabaseClient
  return { tabs: [tab, tab], signups: () => signups }
}

describe('ensureAnonymousSession in a browser with Web Locks', () => {
  it('makes one anonymous user when two tabs start at once', async () => {
    expect('locks' in navigator).toBe(true)
    const { tabs, signups } = twoTabs()

    const ids = await Promise.all(tabs.map((tab) => ensureAnonymousSession(tab)))

    expect(ids).toEqual(['user-1', 'user-1'])
    expect(signups()).toBe(1)
  })
})
