import type { SupabaseClient } from '@supabase/supabase-js'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { createSupabase } from '@/lib/supabase'
import { server } from '@/test/msw-server'
import {
  ANONYMOUS_DISABLED,
  anonymousSession,
  SIGNUP_URL,
  SUPABASE_URL,
} from '@/test/supabase-fixtures'
import { renderWithProviders } from '@/test/test-utils'

import { SessionNotice } from './SessionNotice'

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

describe('SessionNotice', () => {
  it('tells the visitor when the anonymous session could not be started', async () => {
    server.use(http.post(SIGNUP_URL, () => HttpResponse.json(ANONYMOUS_DISABLED, { status: 422 })))
    renderWithProviders(<SessionNotice client={newClient()} />)

    expect(await screen.findByRole('status')).toHaveTextContent(/nothing you do here can be saved/)
    // The server's error text stays out of the page.
    expect(screen.queryByText(/Anonymous sign-ins are disabled/)).not.toBeInTheDocument()
  })

  it('stays silent once the session is started', async () => {
    let signUps = 0
    server.use(
      http.post(SIGNUP_URL, () => {
        signUps += 1
        return HttpResponse.json(anonymousSession())
      }),
    )
    renderWithProviders(<SessionNotice client={newClient()} />)

    await expect.poll(() => signUps).toBe(1)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
