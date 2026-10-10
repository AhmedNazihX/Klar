import { useId, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { FactCard } from '@/components/FactCard'
import { GlassPanel } from '@/components/GlassPanel'

import { restingFacts } from './result-text'

/**
 * "The result rests on": the deciding facts, each with its evidence tag. Change reopens the
 * description. Confirm on an assumed fact sends it back to the engine as the user's statement
 * and runs the checks again (the follow-up loop, P5b): marking it here alone would leave the
 * steps and the class as they were. Panels in `above` go over it, in the same side column (the
 * provider layout's, P23).
 */
export function FactsPanel({
  result,
  onChange,
  onConfirm,
  isBusy,
  above,
}: {
  result: ClassificationResult
  onChange: () => void
  onConfirm: (fact: string) => void
  isBusy: boolean
  above?: ReactNode
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const facts = restingFacts(result)
  const panel = (
    <GlassPanel
      as="aside"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-4 p-6.5 xl:w-[380px] xl:shrink-0"
    >
      <div className="flex flex-col gap-1.5">
        <h2 id={headingId} className="m-0 text-heading-panel text-ink">
          {t('result.facts.heading')}
        </h2>
        <p className="m-0 text-label font-normal text-slate">{t('result.facts.intro')}</p>
      </div>
      <div className="flex flex-col gap-2.5">
        {facts.map((fact) => (
          <FactCard
            key={fact.text}
            fact={fact.text}
            evidence={fact.evidence}
            onChange={onChange}
            onConfirm={() => {
              onConfirm(fact.text)
            }}
            isBusy={isBusy}
          />
        ))}
      </div>
      <p className="m-0 mt-auto text-caption font-normal text-slate">
        {t('result.facts.accuracy')}
      </p>
    </GlassPanel>
  )
  if (!above) return panel
  return (
    <div className="flex min-w-0 flex-col gap-5 xl:w-[380px] xl:shrink-0">
      {above}
      {panel}
    </div>
  )
}
