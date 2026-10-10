import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, OpenQuestion, Reading, StepName } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { LawDate } from '@/components/LawDate'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'
import { SUPPORTED_LANGUAGES } from '@/i18n'
import { cn } from '@/lib/utils'

import { readingsInOrder } from './ambiguous'
import { longDate } from './dates'
import { ProvisionQuote } from './ProvisionQuote'
import { dutiesDate } from './result-text'

/** A year, which tells a dated consequence from one with no date. */
const YEAR = /\b\d{4}\b/

/** What follows if the reading holds, as the engine words it. Its date is the route's under the
 *  result's text; under the original text (the law switch, decision 026 item 11) the route's
 *  original date takes its place, so the card never contradicts the date above. A line whose
 *  route date can't be found is shown as the engine wrote it under both texts. */
function Consequence({
  text,
  result,
}: {
  text: string
  result: ClassificationResult
}): JSX.Element {
  const className = 'm-0 text-body-small text-slate'
  const dates = dutiesDate(result)
  if (dates?.kind !== 'route' || dates.amended === dates.original || !YEAR.test(text)) {
    return <p className={className}>{text}</p>
  }
  const written = SUPPORTED_LANGUAGES.find((language) =>
    text.includes(longDate(dates.amended, language)),
  )
  if (!written) return <p className={className}>{text}</p>
  const original = text.replace(longDate(dates.amended, written), longDate(dates.original, written))
  return (
    <p className={className}>
      <LawDate amended={text} original={original} />
    </p>
  )
}

/** The class a reading gives. A reading that sets no class of its own on the high-risk or the
 *  Art. 5 check says what it rules out ("Not high-risk"), in a neutral pill: the remaining checks
 *  decide the class, so it mustn't look like one. Elsewhere it shows no pill. */
function ReadingClass({ reading, step }: { reading: Reading; step: StepName }): JSX.Element | null {
  const { t } = useTranslation()
  if (reading.risk_class) return <RiskPill kind={reading.risk_class} />
  if (step === 'high_risk') {
    return <StatusPill status="decided">{t('result.steps.notHighRisk')}</StatusPill>
  }
  if (step === 'prohibited') {
    return <StatusPill status="decided">{t('result.steps.noBan')}</StatusPill>
  }
  return null
}

function ReadingCard({
  number,
  reading,
  step,
  result,
}: {
  number: number
  reading: Reading
  step: StepName
  result: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const isApplied = reading.is_applied === true
  const label = t('ambiguous.reading', { number })
  const { citation } = reading
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      data-applied={isApplied || undefined}
      className={cn(
        'flex min-w-0 flex-col items-start gap-3.5 p-6.5',
        isApplied && 'shadow-highlight-high',
      )}
    >
      <div className="flex min-h-[26px] w-full flex-wrap items-center justify-between gap-3">
        <span className="text-caption font-medium text-slate">{label}</span>
        {isApplied && (
          <span className="inline-flex min-h-[26px] items-center rounded-pill bg-lens-blue px-2.5 py-1 text-[13px] leading-tight font-semibold text-white">
            {t('ambiguous.applied')}
          </span>
        )}
      </div>
      <h2 id={headingId} className="m-0 text-[20px] leading-snug font-semibold tracking-[-0.01em]">
        {reading.title ?? label}
      </h2>
      <ReadingClass reading={reading} step={step} />
      <p className="m-0 text-[15px] leading-[1.55] text-ink-2">{reading.explanation}</p>
      {citation && (
        <div className="flex w-full flex-col gap-1.5">
          <ProvisionQuote provisionId={citation.provision_id} result={result} />
          {citation.changed_by_omnibus && (
            <span className="text-micro text-slate">{t('ambiguous.changedByOmnibus')}</span>
          )}
        </div>
      )}
      {reading.consequence && <Consequence text={reading.consequence} result={result} />}
    </GlassPanel>
  )
}

/** Both readings of the open question (E12), side by side on a wide screen: title, the class
 *  it gives, why, the provision it rests on quoted from the corpus in the screen's language at
 *  the result's law version and date (never the result's copy, decision 031), and what follows
 *  if it holds. The stricter one, applied until the question is settled, is marked and comes
 *  last (artboard `ResultAmbiguous`). The model's words are shown as plain text. */
export function ReadingCards({
  question,
  step,
  result,
}: {
  question: OpenQuestion
  /** The step that left the question open, for a reading that sets no class. */
  step: StepName
  result: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <div
      role="group"
      aria-label={t('ambiguous.readings')}
      className="grid min-w-0 items-stretch gap-5 md:grid-cols-2"
    >
      {readingsInOrder(question).map(({ number, reading }) => (
        <ReadingCard key={number} number={number} reading={reading} step={step} result={result} />
      ))}
    </div>
  )
}
