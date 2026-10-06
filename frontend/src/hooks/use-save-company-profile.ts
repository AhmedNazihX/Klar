import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import { saveCompanyProfile, type CompanyProfileInput } from '@/lib/company-profile'
import { supabase } from '@/lib/supabase'

import { anonymousSessionOptions } from './use-anonymous-session'
import { userDataOverviewKey } from './use-user-data-overview'

export type SaveCompanyProfileVariables = {
  inventoryId: string | null
  profile: CompanyProfileInput
  /** The name a new inventory gets when the user has none yet. */
  inventoryName: string
}

/** Saves the company profile onto the user's inventory, then re-reads the overview. */
export function useSaveCompanyProfile(
  client: SupabaseClient | null = supabase,
): UseMutationResult<void, unknown, SaveCompanyProfileVariables> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ inventoryId, profile, inventoryName }) => {
      if (!client) throw new Error('Supabase is not configured.')
      await queryClient.query(anonymousSessionOptions(client))
      await saveCompanyProfile(client, inventoryId, profile, inventoryName)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userDataOverviewKey }),
  })
}
