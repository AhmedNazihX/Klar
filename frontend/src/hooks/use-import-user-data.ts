import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import { importUserData, type ImportCounts } from '@/lib/company-profile'
import { supabase } from '@/lib/supabase'

import { anonymousSessionOptions } from './use-anonymous-session'
import { userDataOverviewKey } from './use-user-data-overview'

/**
 * Restores a file exported from Your data (import_my_data adds its inventories, tools and runs to
 * the user's own). Nothing is classified again. Re-reads the overview afterwards.
 */
export function useImportUserData(
  client: SupabaseClient | null = supabase,
): UseMutationResult<ImportCounts, unknown, File> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file) => {
      if (!client) throw new Error('Supabase is not configured.')
      await queryClient.query(anonymousSessionOptions(client))
      return importUserData(client, file)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: userDataOverviewKey }),
  })
}
