import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import { supabase } from '@/lib/supabase'
import { downloadJson, exportFileName, exportUserData } from '@/lib/user-data'

import { withAnonymousSession } from './use-anonymous-session'

/**
 * "Download everything": reads the user's data (export_my_data) and saves it as a JSON file that
 * Import restores. The file is made in the browser; nothing else is sent anywhere.
 */
export function useExportUserData(
  client: SupabaseClient | null = supabase,
): UseMutationResult<void, unknown, void> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const document = await exportUserData(await withAnonymousSession(queryClient, client))
      downloadJson(document, exportFileName(new Date()))
    },
  })
}
