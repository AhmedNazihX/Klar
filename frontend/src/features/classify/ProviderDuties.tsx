import { useId, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, Obligation, ObligationGroup } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { ObligationItem } from '@/components/ObligationItem'
import { dutiesProgress } from '@/features/obligations/obligation-list'
import { useDutyTicks } from '@/hooks/use-duty-progress'
import { useLanguage } from '@/hooks/use-language'
import type { ToolTicks as Ticks } from '@/hooks/use-tool-ticks'
import { tickKey } from '@/lib/duty-progress'

import { OriginalDatesNote } from './OriginalDatesNote'
import { provisionName } from './provision-names'
import { DUTY_GROUPS, TECHNICAL_DOCUMENTATION_ARTICLE } from './provider-layout'
import { GpaiNote } from './ProviderNotes'
import { DUTY_REFERENCE_WIDTH, dutyLabel, dutyNote, isTransparencyDuty } from './result-text'

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
  toolId,
  ticks,
}: {
  duties: readonly Obligation[]
  toolId: string
  ticks: Ticks
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const docLabel = useDocLabel()
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {duties.map((duty) => {
        const key = tickKey(duty)
        return (
          <ObligationItem
            key={duty.key ?? `${duty.article}:${duty.duty}`}
            label={dutyLabel(duty, language)}
            reference={provisionName(duty.article, language)}
            referenceWidth={DUTY_REFERENCE_WIDTH[language]}
            note={dutyNote(t, duty, language)}
            tag={duty.legacy ? t('result.legacy.tag') : undefined}
            // As on the Obligations screen: a duty with nothing to tick off gets no box.
            isInformational={key === null}
            docLabel={docLabel(duty)}
            documentId={duty.document}
            toolId={toolId}
            checked={key !== null && ticks.done.has(key)}
            onCheckedChange={key === null ? undefined : (isDone) => ticks.onTick(key, isDone)}
          />
        )
      })}
    </ul>
  )
}

/** "3 of 21 done", over the duties that can be ticked off. */
function DoneCount({
  toolId,
  duties,
}: {
  toolId: string
  duties: readonly Obligation[]
}): ReactNode {
  const { t } = useTranslation()
  const ticks = useDutyTicks()
  const progress = dutiesProgress(toolId, duties, ticks.data ?? [])
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
  toolId,
  duties,
  children,
}: {
  id?: string
  heading: ReactNode
  intro?: ReactNode
  toolId: string
  /** Every duty the panel lists, for its count. */
  duties: readonly Obligation[]
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
          <DoneCount toolId={toolId} duties={duties} />
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
  toolId,
  ticks,
}: {
  group: ObligationGroup
  duties: readonly Obligation[]
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
      <DutyList duties={duties} toolId={toolId} ticks={ticks} />
    </section>
  )
}

/**
 * "What you need to do as the provider" (artboard `ResultProvider`): the duty count, then the
 * provider's duties in C9's three groups (Build it right, Prove it, After launch), each with its
 * box, its Art. 111(2) marking and its draft; the technical documentation opens its skeleton.
 */
export function ProviderDutiesPanel({
  result,
  groups,
  toolId,
  ticks,
}: {
  result: ClassificationResult
  groups: Record<ObligationGroup, Obligation[]>
  toolId: string
  ticks: Ticks
}): JSX.Element {
  const { t } = useTranslation()
  const shown = DUTY_GROUPS.filter((group) => groups[group].length > 0)
  // The engine lists no duties under the original text (decision 020): it says so, not "none".
  const intro =
    result.law_version === 'original' ? t('result.todo.notModelled') : t('result.provider.intro')
  return (
    <DutiesSection
      heading={t('result.provider.heading')}
      intro={
        <>
          <p className="m-0 max-w-[620px] text-body-small text-slate">{intro}</p>
          <OriginalDatesNote result={result} />
          <GpaiNote result={result} />
        </>
      }
      toolId={toolId}
      duties={shown.flatMap((group) => groups[group])}
    >
      {shown.map((group) => (
        <DutyGroup key={group} group={group} duties={groups[group]} toolId={toolId} ticks={ticks} />
      ))}
    </DutiesSection>
  )
}
