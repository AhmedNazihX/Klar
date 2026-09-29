import type { SupabaseClient } from '@supabase/supabase-js'

/**
 * Make sure this browser has a session and return its user id. It reuses the stored session, and
 * signs in anonymously only when there is none (INIT › Storage: each visitor gets an anonymous
 * session). The id is the `auth.uid()` that row-level security keys the user's data on.
 */
export async function ensureAnonymousSession(client: SupabaseClient): Promise<string> {
  const stored = await client.auth.getSession()
  if (stored.error) throw stored.error
  if (stored.data.session) return stored.data.session.user.id

  const signedIn = await client.auth.signInAnonymously()
  if (signedIn.error) throw signedIn.error
  const user = signedIn.data.user
  if (!user) throw new Error('Anonymous sign-in returned no user.')
  return user.id
}
