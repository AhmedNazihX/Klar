import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import { supabase } from '@/lib/supabase'
import { deleteUserData } from '@/lib/user-data'

import { withAnonymousSession } from './use-anonymous-session'

/**
 * "Delete my data": deletes everything stored (delete_my_data) and ends the session. The
 * sign-out it ends with is what clears this tab's cache and draft, as in every other open tab
 * (useForgetOnSignOut, at the app's root).
 */
export function useDeleteUserData(
  client: SupabaseClient | null = supabase,
): UseMutationResult<void, unknown, void> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => deleteUserData(await withAnonymousSession(queryClient, client)),
  })
}
