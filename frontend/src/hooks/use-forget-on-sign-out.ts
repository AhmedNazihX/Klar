import type { SupabaseClient } from '@supabase/supabase-js'
import { hashKey, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { clearDraft } from '@/features/classify/classification-store'
import { EMPTY_OVERVIEW } from '@/lib/company-profile'
import { supabase } from '@/lib/supabase'

import { userDataOverviewKey } from './use-user-data-overview'

/**
 * Forgets the ended session in this tab: the description draft and every cached query (the
 * user's data, runs, the session itself). The sidebar's overview is emptied rather than removed,
 * as it stays on screen. The app frame (SessionNotice) then starts a new, empty anonymous
 * session, so saving works again without a reload.
 */
function forgetSession(queryClient: QueryClient): void {
  clearDraft()
  queryClient.setQueryData(userDataOverviewKey, EMPTY_OVERVIEW)
  const overviewHash = hashKey(userDataOverviewKey)
  queryClient.removeQueries({ predicate: (query) => query.queryHash !== overviewHash })
}

/**
 * Forgets the session whenever it ends: after Delete my data in this tab, and in every other open
 * tab too, which supabase-js tells of the sign-out. Mounted once, at the root of the app.
 */
export function useForgetOnSignOut(client: SupabaseClient | null = supabase): void {
  const queryClient = useQueryClient()
  useEffect(() => {
    if (!client) return
    // The callback stays synchronous: supabase-js runs it while it holds its auth lock.
    const { data } = client.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_OUT') forgetSession(queryClient)
    })
    return () => data.subscription.unsubscribe()
  }, [client, queryClient])
}
