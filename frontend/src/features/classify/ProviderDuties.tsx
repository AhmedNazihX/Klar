import { useId, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, Obligation, ObligationGroup } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { progressOver } from '@/features/obligations/obligation-list'
import { useLanguage } from '@/hooks/use-language'
import type { ToolTicks as Ticks } from '@/hooks/use-tool-ticks'

import { DutyItem } from './DutyItem'
import { OriginalDatesNote } from './OriginalDatesNote'
import { DUTY_GROUPS, TECHNICAL_DOCUMENTATION_ARTICLE } from './provider-layout'
import { GpaiNote } from './ProviderNotes'
import { dutyNote, isTransparencyDuty } from './result-text'

function useDocLabel(): (duty: Obligation) => string {
  const { t } = useTranslation()
  return (duty) => {
    if (duty.article === TECHNICAL_DOCUMENTATION_ARTICLE) return t('result.provider.openSkeleton')
    return isTransparencyDuty(duty)
      ? t('result.todo.draftDisclosure')
      : t('result.todo.draftDocument')
  }
}

/** Duties with their boxes, the Art. 111(2) marking and their draft documents (as in P5). */
export function DutyList({
  duties,
  result,
  toolId,
  ticks,
}: {
  duties: readonly Obligation[]
  /** The result that lists the duties. */
  result: ClassificationResult
  toolId: string
  ticks: Ticks
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const docLabel = useDocLabel()
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {duties.map((duty) => (
        <DutyItem
          key={duty.key ?? `${duty.article}:${duty.duty}`}
          duty={duty}
          result={result}
          toolId={toolId}
          note={dutyNote(t, duty, language)}
          docLabel={docLabel(duty)}
          done={ticks.done}
          onTick={ticks.onTick}
        />
      ))}
    </ul>
  )
}

/** "3 of 21 done", over the duties that can be ticked off. */
function DoneCount({
  duties,
  done,
}: {
  duties: readonly Obligation[]
  done: ReadonlySet<string>
}): ReactNode {
  const { t } = useTranslation()
  const progress = progressOver(duties, done)
  if (progress.total === 0) return null
  return (
    <span className="text-caption font-normal whitespace-nowrap text-slate">
      {t('obligations.card.done', progress)}
    </span>
  )
}

/** A panel of duties: its heading with the count, an intro, then the lists. */
export function DutiesSection({
  id,
  heading,
  intro,
  duties,
  done,
  children,
}: {
  id?: string
  heading: ReactNode
  intro?: ReactNode
  /** Every duty the panel lists, for its count. */
  duties: readonly Obligation[]
  /** The obligation keys ticked off on the tool. */
  done: ReadonlySet<string>
  children: ReactNode
}): JSX.Element {
  const headingId = useId()
  return (
    <GlassPanel
      as="section"
      id={id}
      tabIndex={id ? -1 : undefined}
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-4 px-7 py-6.5"
    >
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id={headingId} className="m-0 text-heading-panel text-ink">
            {heading}
          </h2>
          <DoneCount duties={duties} done={done} />
        </div>
        {intro}
      </div>
      {children}
    </GlassPanel>
  )
}

/** One group of the provider's duties: its name, when it applies, and its duties. */
function DutyGroup({
  group,
  duties,
  result,
  toolId,
  ticks,
}: {
  group: ObligationGroup
  duties: readonly Obligation[]
  result: ClassificationResult
  toolId: string
  ticks: Ticks
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="flex flex-col">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 pt-2.5 pb-1.5">
        <h3 id={headingId} className="m-0 text-body-small font-semibold text-ink">
          {t(`result.provider.group.${group}.title`)}
        </h3>
        <span className="text-caption font-normal text-slate">
          {t(`result.provider.group.${group}.note`)}
        </span>
      </div>
      <DutyList duties={duties} result={result} toolId={toolId} ticks={ticks} />
    </section>
  )
}

/**
 * "What you need to do as the provider" (artboard `ResultProvider`): the duty count, then the
 * provider's duties in C9's three groups (Build it right, Prove it, After launch), each with its
 * box, its Art. 111(2) marking and its draft; the technical documentation opens its skeleton.
 * `heading` replaces the title where the duties follow from a reading, not a decided class.
 */
export function ProviderDutiesPanel({
  result,
  groups,
  toolId,
  ticks,
  heading,
}: {
  result: ClassificationResult
  groups: Record<ObligationGroup, Obligation[]>
  toolId: string
  ticks: Ticks
  heading?: string
}): JSX.Element {
  const { t } = useTranslation()
  const shown = DUTY_GROUPS.filter((group) => groups[group].length > 0)
  // The engine lists no duties under the original text (decision 020): it says so, not "none".
  const intro =
    result.law_version === 'original' ? t('result.todo.notModelled') : t('result.provider.intro')
  return (
    <DutiesSection
      heading={heading ?? t('result.provider.heading')}
      intro={
        <>
          <p className="m-0 max-w-[620px] text-body-small text-slate">{intro}</p>
          <OriginalDatesNote result={result} />
          <GpaiNote result={result} />
        </>
      }
      duties={shown.flatMap((group) => groups[group])}
      done={ticks.done}
    >
      {shown.map((group) => (
        <DutyGroup
          key={group}
          group={group}
          duties={groups[group]}
          result={result}
          toolId={toolId}
          ticks={ticks}
        />
      ))}
    </DutiesSection>
  )
}
