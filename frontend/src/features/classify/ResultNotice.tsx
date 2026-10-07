import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Notice } from '@/components/Notice'

/**
 * The result's own disclaimer, as the engine wrote it, and the law text the answers cite. The
 * frame's closing Notice follows it on every screen ("Guidance, not legal advice. Klar is an AI
 * system."), so both halves stay visible.
 */
export function ResultNotice({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  return (
    <Notice>
      {result.disclaimer}
      {result.law_text && ` ${t('result.notice', { celex: result.law_text.celex })}`}
    </Notice>
  )
}
