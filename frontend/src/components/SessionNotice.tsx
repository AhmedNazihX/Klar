import type { SupabaseClient } from '@supabase/supabase-js'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { useAnonymousSession } from '@/hooks/use-anonymous-session'
import { supabase } from '@/lib/supabase'

/**
 * Starts the visitor's anonymous session (INIT › Storage: every visitor gets one) and says so,
 * without blocking the page, when that fails: the app still works, but nothing can be saved.
 * The error's own text is not shown, as it may carry server details.
 */
export function SessionNotice({
  client = supabase,
}: {
  client?: SupabaseClient | null
}): JSX.Element | null {
  const { t } = useTranslation()
  const session = useAnonymousSession(client)
  if (!session.isError) return null
  return (
    <p role="status" className="rounded-2xl px-4 py-2 text-sm text-ink glass-thin">
      {t('session.failed')}
    </p>
  )
}
