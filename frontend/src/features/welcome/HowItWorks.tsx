import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'

const STEPS = ['describe', 'answer', 'result'] as const

/** "How it works" in three steps. */
export function HowItWorks(): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-3.5 p-6.5">
      <h2 id={headingId} className="m-0 text-heading-small text-ink">
        {t('welcome.how.heading')}
      </h2>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {STEPS.map((step, index) => (
          <li key={step} className="flex items-baseline gap-3">
            <span aria-hidden="true" className="w-4 shrink-0 font-semibold text-lens-blue">
              {index + 1}
            </span>
            <span className="text-body text-ink">{t(`welcome.how.${step}`)}</span>
          </li>
        ))}
      </ol>
    </GlassPanel>
  )
}
