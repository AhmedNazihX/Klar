import { useSearch } from '@tanstack/react-router'

import type { LawVersion } from '@/components/LawSwitch'

/**
 * The law version on show in the app: the `law` search param the app frame's switch sets
 * (routes/app.tsx), amended unless it says original.
 */
export function useLawVersion(): LawVersion {
  const search: { law?: unknown } = useSearch({ strict: false })
  return search.law === 'original' ? 'original' : 'amended'
}
