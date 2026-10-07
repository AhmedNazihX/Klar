import type { SupabaseClient } from '@supabase/supabase-js'

/** The Web Lock that lets one tab of this browser at a time find or create the session. */
export const ANONYMOUS_SESSION_LOCK = 'klar.anonymous-session'

/** The browser's Web Locks, or undefined where there are none (jsdom, older browsers, http pages). */
function webLocks(): LockManager | undefined {
  return 'locks' in navigator ? navigator.locks : undefined
}

async function findOrCreateSession(client: SupabaseClient): Promise<string> {
  const stored = await client.auth.getSession()
  if (stored.error) throw stored.error
  if (stored.data.session) return stored.data.session.user.id

  const signedIn = await client.auth.signInAnonymously()
  if (signedIn.error) throw signedIn.error
  const user = signedIn.data.user
  if (!user) throw new Error('Anonymous sign-in returned no user.')
  return user.id
}

/**
 * Make sure this browser has a session and return its user id. It reuses the stored session, and
 * signs in anonymously only when there is none (INIT › Storage: each visitor gets an anonymous
 * session). The id is the `auth.uid()` that row-level security keys the user's data on.
 *
 * Every tab shares one stored session, so the look-up and the sign-in run under a cross-tab lock:
 * a second tab starting at the same moment waits, then finds the first tab's stored session
 * instead of making a second anonymous user. Where the browser has no Web Locks, the two steps
 * run unlocked, and two tabs starting at the very same moment can each still sign in.
 */
export async function ensureAnonymousSession(client: SupabaseClient): Promise<string> {
  const locks = webLocks()
  if (!locks) return findOrCreateSession(client)
  return locks.request(ANONYMOUS_SESSION_LOCK, () => findOrCreateSession(client))
}
