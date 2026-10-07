import type { SupabaseClient } from '@supabase/supabase-js'
import {
  hashKey,
  useMutation,
  useQueryClient,
  type QueryClient,
  type UseMutationResult,
} from '@tanstack/react-query'

import { clearDraft } from '@/features/classify/classification-store'
import { EMPTY_OVERVIEW } from '@/lib/company-profile'
import { supabase } from '@/lib/supabase'
import { deleteUserData } from '@/lib/user-data'

import { anonymousSessionOptions } from './use-anonymous-session'
import { userDataOverviewKey } from './use-user-data-overview'

/**
 * Forgets the ended session in this tab: the description draft and every cached query (runs,
 * the session itself). The sidebar's overview is emptied rather than removed, as it stays on
 * screen. The app frame (SessionNotice) then starts a new, empty anonymous session, so saving
 * works again without a reload.
 */
function forgetSession(queryClient: QueryClient): void {
  clearDraft()
  queryClient.setQueryData(userDataOverviewKey, EMPTY_OVERVIEW)
  const overviewHash = hashKey(userDataOverviewKey)
  queryClient.removeQueries({ predicate: (query) => query.queryHash !== overviewHash })
}

/** "Delete my data": deletes everything stored (delete_my_data) and ends the session. */
export function useDeleteUserData(
  client: SupabaseClient | null = supabase,
): UseMutationResult<void, unknown, void> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      if (!client) throw new Error('Supabase is not configured.')
      await queryClient.query(anonymousSessionOptions(client))
      await deleteUserData(client)
    },
    onSuccess: () => forgetSession(queryClient),
  })
}
