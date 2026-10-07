import type { TFunction } from 'i18next'
import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { CheckProgress, type CheckProgressStep } from '@/components/CheckProgress'
import { GlassPanel } from '@/components/GlassPanel'
import type { ClassifyFailure } from '@/hooks/use-classify'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'

import {
  CHECK_IDS,
  checkNumber,
  checkState,
  didContinue,
  type CheckId,
  type CheckState,
  type ProgressState,
} from './classify-progress'
import { failureReason } from './failure-reason'
import { provisionName } from './provision-names'
import { annexLabel } from './result-text'

/** "Stopped at check N of 4", or that the checks never started. */
function stoppedTitle(t: TFunction, progress: ProgressState): string {
  const at = progress.stoppedAt
  const hasStarted = progress.facts !== null || progress.started.length > 0
  if (at === null || !hasStarted) return t('progress.stopped.notStarted')
  const number = checkNumber(at)
  if (number !== null) return t('progress.stopped.atCheck', { number })
  return at === 'facts' ? t('progress.stopped.atFacts') : t('progress.stopped.atDuties')
}

type RowContext = {
  t: TFunction
  language: Language
  progress: ProgressState
  failure: ClassifyFailure | null
}

function doneOutcome(id: Exclude<CheckId, 'facts'>, { t, progress }: RowContext): string {
  const step = progress.steps[id]
  if (step?.result.status === 'legally_ambiguous') return t('progress.outcome.ambiguous')
  if (id === 'high_risk') {
    return step && step.matches.length > 0
      ? t('progress.outcome.listed')
      : t('progress.outcome.notListed')
  }
  if (id === 'scope' && didContinue(id, progress)) return t('progress.outcome.inScope')
  if (id === 'prohibited' && didContinue(id, progress)) return t('progress.outcome.noMatch')
  return t('progress.outcome.checked')
}

/** A finished row's line: its outcome and article, and the Annex points a High-risk check cited. */
function doneRow(id: CheckId, context: RowContext): Partial<CheckProgressStep> {
  const { t, language, progress } = context
  if (id === 'facts') {
    const facts = progress.facts
    return {
      detail: facts && t('progress.factsFound', { count: facts.count, questions: facts.questions }),
    }
  }
  const outcome = doneOutcome(id, context)
  return {
    detail: t('progress.detail', { outcome, reference: t(`progress.reference.${id}`) }),
    matches: (progress.steps[id]?.matches ?? []).map((point) => {
      const name = provisionName(point, language)
      const label = annexLabel(t, point)
      return { id: point, label: label ? `${name}: ${label}` : name }
    }),
  }
}

function rowDetail(
  id: CheckId,
  state: CheckState,
  context: RowContext,
): Partial<CheckProgressStep> {
  const { t, progress, failure } = context
  const reference = t(`progress.reference.${id}`)
  switch (state) {
    case 'error':
      return { detail: failure ? failureReason(t, failure) : t('progress.reason.check') }
    case 'running':
      return { detail: t(`progress.runningDetail.${id}`) }
    case 'paused':
      return { detail: t('progress.paused', { reference }) }
    case 'waiting':
      return {
        detail: progress.stoppedAt ? t('progress.notRun') : t('progress.waiting', { reference }),
      }
    case 'done':
      return doneRow(id, context)
  }
}

/** The check list's rows from what the stream has said so far. */
function progressRows(context: RowContext, isRunning: boolean): CheckProgressStep[] {
  return CHECK_IDS.map((id) => {
    const state = checkState(id, context.progress, isRunning)
    return { id, name: context.t(`progress.check.${id}`), state, ...rowDetail(id, state, context) }
  })
}

export type ProgressPanelProps = {
  progress: ProgressState
  isRunning: boolean
  failure: ClassifyFailure | null
  onTryAgain: () => void
  onSaveForLater: () => void
}

/**
 * The checks beside the description, in the Act's order (artboards `Classify`, `ClassifyError`).
 * When a run stops it says where and why, keeps the description, offers Try again and Save for
 * later, and shows no class.
 */
export function ProgressPanel({
  progress,
  isRunning,
  failure,
  onTryAgain,
  onSaveForLater,
}: ProgressPanelProps): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const rows = progressRows({ t, language, progress, failure }, isRunning)
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-4.5 p-6 xl:w-[400px] xl:shrink-0"
    >
      <div className="flex flex-col gap-1">
        <h2 id={headingId} className="m-0 text-heading-small text-ink">
          {t('progress.heading')}
        </h2>
        <p className="m-0 text-caption font-normal text-slate">
          {failure ? stoppedTitle(t, progress) : t('progress.subtitle')}
        </p>
      </div>
      {failure && (
        <div role="alert" className="flex flex-col gap-3 rounded-card-small px-4 py-3.5 glass-thin">
          <p className="m-0 text-body-small font-semibold text-ink">
            {t('progress.stopped.title')}
          </p>
          <p className="m-0 text-caption font-normal text-ink-2">{failureReason(t, failure)}</p>
          <p className="m-0 text-caption font-normal text-ink-2">{t('progress.stopped.body')}</p>
          <div className="flex flex-wrap gap-2.5">
            <Button size="sm" onClick={onTryAgain}>
              {t('progress.stopped.tryAgain')}
            </Button>
            <Button size="sm" variant="ghost" onClick={onSaveForLater}>
              {t('progress.stopped.saveForLater')}
            </Button>
          </div>
        </div>
      )}
      <CheckProgress steps={rows} />
      <p className="m-0 mt-auto rounded-card-small px-3.5 py-3 text-caption font-normal text-ink-2 glass-thin">
        {t('progress.accuracy')}
      </p>
    </GlassPanel>
  )
}
