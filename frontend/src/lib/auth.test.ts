import type { SupabaseClient } from '@supabase/supabase-js'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { server } from '@/test/msw-server'

import { ensureAnonymousSession } from './auth'
import { createSupabase } from './supabase'

const SUPABASE_URL = 'http://127.0.0.1:54321'
const SIGNUP_URL = `${SUPABASE_URL}/auth/v1/signup`
const USER_ID = '6f1c1d3e-8f55-4c55-9d7e-1a2b3c4d5e6f'

// What GoTrue returns for an anonymous sign-in.
function anonymousSession(): Record<string, unknown> {
  const now = Math.floor(Date.now() / 1000)
  return {
    access_token: 'test-access-token',
    token_type: 'bearer',
    expires_in: 3600,
    expires_at: now + 3600,
    refresh_token: 'test-refresh-token',
    user: {
      id: USER_ID,
      aud: 'authenticated',
      role: 'authenticated',
      is_anonymous: true,
      app_metadata: {},
      user_metadata: {},
      created_at: new Date().toISOString(),
    },
  }
}

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
    server.use(
      http.post(SIGNUP_URL, () =>
        HttpResponse.json(
          {
            code: 422,
            error_code: 'anonymous_provider_disabled',
            msg: 'Anonymous sign-ins are disabled',
          },
          { status: 422 },
        ),
      ),
    )
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
