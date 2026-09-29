import type { SupabaseClient } from '@supabase/supabase-js'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { server } from '@/test/msw-server'
import {
  ANONYMOUS_DISABLED,
  anonymousSession,
  SIGNUP_URL,
  SUPABASE_URL,
  USER_ID,
} from '@/test/supabase-fixtures'

import { ensureAnonymousSession } from './auth'
import { createSupabase } from './supabase'

let client: SupabaseClient | null = null

function newClient(): SupabaseClient {
  client = createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' })
  if (!client) throw new Error('expected a client')
  return client
}

afterEach(async () => {
  await client?.auth.stopAutoRefresh()
  client = null
})

describe('ensureAnonymousSession', () => {
  it('signs in anonymously once, then reuses the stored session', async () => {
    let signUps = 0
    server.use(
      http.post(SIGNUP_URL, () => {
        signUps += 1
        return HttpResponse.json(anonymousSession())
      }),
    )
    const supabase = newClient()

    await expect(ensureAnonymousSession(supabase)).resolves.toBe(USER_ID)
    await expect(ensureAnonymousSession(supabase)).resolves.toBe(USER_ID)
    expect(signUps).toBe(1)
  })

  it('raises the auth error when anonymous sign-ins are refused', async () => {
    server.use(http.post(SIGNUP_URL, () => HttpResponse.json(ANONYMOUS_DISABLED, { status: 422 })))
    await expect(ensureAnonymousSession(newClient())).rejects.toThrow(
      /Anonymous sign-ins are disabled/,
    )
  })
})

describe('createSupabase', () => {
  it('returns no client when Supabase is not configured', () => {
    expect(createSupabase(null)).toBeNull()
  })
})
