import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { useLawVersion } from '@/hooks/use-law-version'

/**
 * Under the original text only the route dates swap; the duties stay the amended text's
 * (decision 026 item 11), and every duty list says so: the summary's and the reviewer view's.
 * Nothing shows under the amended text, on a result run under the original, or without duties.
 */
export function OriginalDatesNote({
  result,
}: {
  result: ClassificationResult
}): JSX.Element | null {
  const { t } = useTranslation()
  const law = useLawVersion()
  const hasDuties = (result.obligations ?? []).length > 0
  if (law !== 'original' || result.law_version !== 'amended' || !hasDuties) return null
  return (
    <p role="note" className="m-0 max-w-[620px] text-body-small text-ink-2">
      {t('result.todo.originalDates')}
    </p>
  )
}
