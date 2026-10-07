import type { SupabaseClient } from '@supabase/supabase-js'
import { hashKey, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { classificationRunKey, clearDraft } from '@/features/classify/classification-store'
import { EMPTY_OVERVIEW } from '@/lib/company-profile'
import { supabase } from '@/lib/supabase'

import { endAnonymousSession, hasAnonymousSession } from './use-anonymous-session'
import { userDataKey, userDataOverviewKey } from './use-user-data-overview'

/**
 * Forgets the ended session in this tab: the description draft, the cached user data and runs.
 * The sidebar's overview is emptied rather than removed, as it stays on screen; a read of it
 * still under way is cancelled first, so its answer can't bring the deleted profile back. The
 * session is only marked as ended: a new one starts when this tab next reads or writes the user's
 * data, so an open tab that merely hears of the sign-out never signs in by itself (each sign-in
 * makes an anonymous user).
 */
function forgetSession(queryClient: QueryClient): void {
  clearDraft()
  // The cancel takes effect at once (it rolls the query back to before the read), so the empty
  // overview set next is what stays; only its promise settles later.
  void queryClient.cancelQueries({ queryKey: userDataOverviewKey, exact: true })
  queryClient.setQueryData(userDataOverviewKey, EMPTY_OVERVIEW)
  const overviewHash = hashKey(userDataOverviewKey)
  queryClient.removeQueries({
    queryKey: userDataKey,
    predicate: (query) => query.queryHash !== overviewHash,
  })
  queryClient.removeQueries({ queryKey: classificationRunKey })
  endAnonymousSession(queryClient)
}

/**
 * Forgets the session whenever it ends: after Delete my data in this tab, and in every other open
 * tab too, which supabase-js tells of the sign-out. A tab that holds no session yet has nothing
 * to forget: at start-up supabase-js signs out a stored session that is no longer valid while the
 * session's query is still loading, and that load goes on. After a forget, this tab starts no
 * session on focus or reconnect, and its next one comes through the cross-tab lock, so it takes a
 * session another tab has started instead of making a second. Mounted once, at the root of the app.
 */
export function useForgetOnSignOut(client: SupabaseClient | null = supabase): void {
  const queryClient = useQueryClient()
  useEffect(() => {
    if (!client) return
    // The callback stays synchronous: supabase-js runs it while it holds its auth lock.
    const { data } = client.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_OUT' && hasAnonymousSession(queryClient)) forgetSession(queryClient)
    })
    return () => data.subscription.unsubscribe()
  }, [client, queryClient])
}
