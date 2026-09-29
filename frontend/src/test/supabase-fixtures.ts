// Supabase Auth (GoTrue) responses for MSW handlers.
export const SUPABASE_URL = 'http://127.0.0.1:54321'
export const SIGNUP_URL = `${SUPABASE_URL}/auth/v1/signup`
export const USER_ID = '6f1c1d3e-8f55-4c55-9d7e-1a2b3c4d5e6f'

/** What GoTrue returns for an anonymous sign-in. */
export function anonymousSession(): Record<string, unknown> {
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

/** What GoTrue returns when anonymous sign-ins are switched off. */
export const ANONYMOUS_DISABLED = {
  code: 422,
  error_code: 'anonymous_provider_disabled',
  msg: 'Anonymous sign-ins are disabled',
}
