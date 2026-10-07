import { useId, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { FactCard } from '@/components/FactCard'
import { GlassPanel } from '@/components/GlassPanel'

/**
 * "The result rests on": the deciding facts, each with its evidence tag. Confirming an assumed
 * fact marks it stated on this screen; Change reopens the description. Sending the answers back
 * to the engine is the follow-up loop's (P5b).
 */
export function FactsPanel({
  result,
  onChange,
}: {
  result: ClassificationResult
  onChange: () => void
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const [confirmed, setConfirmed] = useState<ReadonlySet<string>>(new Set())
  const deciding = result.deciding_facts ?? []
  const facts = deciding.length > 0 ? deciding : result.facts
  // A fact's text is its identity: the engine lists each fact once.
  const unique = [...new Map(facts.map((fact) => [fact.text, fact])).values()]
  return (
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
        {unique.map((fact) => {
          const evidence =
            fact.evidence === 'assumed' && confirmed.has(fact.text) ? 'stated' : fact.evidence
          return (
            <FactCard
              key={fact.text}
              fact={fact.text}
              evidence={evidence}
              onChange={onChange}
              onConfirm={() => {
                setConfirmed((previous) => new Set([...previous, fact.text]))
              }}
            />
          )
        })}
      </div>
      <p className="m-0 mt-auto text-caption font-normal text-slate">
        {t('result.facts.accuracy')}
      </p>
    </GlassPanel>
  )
}
