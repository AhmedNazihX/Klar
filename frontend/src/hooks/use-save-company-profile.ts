import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import { saveCompanyProfile, type CompanyProfileInput } from '@/lib/company-profile'
import { supabase } from '@/lib/supabase'

import { withAnonymousSession } from './use-anonymous-session'
import { userDataKey } from './use-user-data-overview'

export type SaveCompanyProfileVariables = {
  inventoryId: string | null
  profile: CompanyProfileInput
  /** The name a new inventory gets when the user has none yet. */
  inventoryName: string
}

/** Saves the company profile onto the user's inventory, then re-reads every user-data query. */
export function useSaveCompanyProfile(
  client: SupabaseClient | null = supabase,
): UseMutationResult<void, unknown, SaveCompanyProfileVariables> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ inventoryId, profile, inventoryName }) => {
      const sessionClient = await withAnonymousSession(queryClient, client)
      await saveCompanyProfile(sessionClient, inventoryId, profile, inventoryName)
    },
    // The overview and Your data's counts (profiles, storage) both change.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userDataKey }),
  })
}
