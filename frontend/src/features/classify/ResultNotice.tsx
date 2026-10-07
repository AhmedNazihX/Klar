import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Notice } from '@/components/Notice'

/**
 * The result's disclaimer and the law text the answers cite. The frame's closing Notice follows it
 * on every screen ("Guidance, not legal advice. Klar is an AI system."), so both halves stay
 * visible. A fresh run shows the disclaimer the engine wrote; a result read back from the user's
 * data shows the app's own (the browser wrote the stored one, P3), after a line saying Klar
 * doesn't re-check it.
 */
export function ResultNotice({
  result,
  isStored = false,
}: {
  result: ClassificationResult
  isStored?: boolean
}): JSX.Element {
  const { t } = useTranslation()
  // A stored result from before the law text carried its CELEX number has none to name.
  const celex: string | undefined = result.law_text?.celex
  return (
    <>
      {isStored && <Notice>{t('result.stored.notice')}</Notice>}
      <Notice>
        {isStored ? t('result.stored.disclaimer') : result.disclaimer}
        {celex && ` ${t('result.notice', { celex })}`}
      </Notice>
    </>
  )
}
