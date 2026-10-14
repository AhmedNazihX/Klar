import type { ClassificationResult, Obligation } from '@/api'
import { useLanguage } from '@/hooks/use-language'
import { useLawVersion } from '@/hooks/use-law-version'
import { useReliefNotes } from '@/hooks/use-relief-notes'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'

import { isRelieved, reliefNote } from './relief'

/** The relief note for a duty of `result`, in the active language, or null when the company gets
 *  none: the obligations table's note for the duty's key, looked up once for `result`'s roles and
 *  class, and wanted for an SME or a small mid-cap only (`isRelieved`). A duty list calls this
 *  once and hands each `DutyItem` its note. */
export function useDutyRelief(result: ClassificationResult): (duty: Obligation) => string | null {
  const language = useLanguage()
  const shown = useLawVersion()
  const sizeClass = useUserDataOverview().data?.profile?.sizeClass
  const table = useReliefNotes(result, isRelieved(sizeClass, shown))
  return (duty) => (duty.key && table ? reliefNote(table[duty.key], language) : null)
}
