import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { useLanguage } from '@/hooks/use-language'

import { banDecisionNote, banPoints } from './ban'
import { provisionName } from './provision-names'
import { ProvisionQuote } from './ProvisionQuote'

/** "Why the checks stopped": each Art. 5(1) point the ban rests on, quoted from the corpus in
 *  the screen's language, and what the Art. 5 step's decision adds to the verdict and the facts
 *  beside it (a point that applies only later), never a repeat of them. */
export function WhyChecksStopped({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const points = banPoints(result)
  const note = banDecisionNote(result)
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-3.5 px-7 py-6"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id={headingId} className="m-0 text-[18px] font-semibold text-ink">
          {t('prohibited.why.heading')}
        </h2>
        {points.length > 0 && (
          <span className="text-caption font-semibold text-ink">
            {points.map((point) => provisionName(point, language)).join(', ')}
          </span>
        )}
      </div>
      {points.map((point) => (
        <ProvisionQuote key={point} provisionId={point} result={result} />
      ))}
      {note && <p className="m-0 text-label font-normal text-slate">{note}</p>}
    </GlassPanel>
  )
}
