import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'

import { ProvisionQuote } from './ProvisionQuote'

/** The paragraphs the tile quotes: the fine for a prohibited practice, and the SME rule. */
const FINE_PROVISIONS = ['art:99:3', 'art:99:6'] as const

/** The maximum fine for a prohibited practice (decision 026 item 1): the amount in short, then
 *  Art. 99(3) and Art. 99(6) quoted word for word from the corpus. */
export function FineTile({
  result,
}: {
  result: Pick<ClassificationResult, 'law_version' | 'as_of'>
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-4 px-7 py-6"
    >
      <div className="flex flex-col gap-x-6 gap-y-2 md:flex-row md:items-center">
        <div className="flex shrink-0 flex-col gap-1">
          <h2 id={headingId} className="m-0 text-caption font-normal text-slate">
            {t('prohibited.fine.heading')}
          </h2>
          <span className="text-[28px] leading-tight font-semibold tracking-[-0.02em] text-ink">
            {t('prohibited.fine.amount')}
          </span>
        </div>
        <p className="m-0 text-label font-normal text-ink-2">{t('prohibited.fine.body')}</p>
      </div>
      {FINE_PROVISIONS.map((provisionId) => (
        <ProvisionQuote key={provisionId} provisionId={provisionId} result={result} />
      ))}
    </GlassPanel>
  )
}
