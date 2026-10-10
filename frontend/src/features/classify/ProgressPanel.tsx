import type { TFunction } from 'i18next'
import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import {
  CheckProgress,
  type CheckProgressState,
  type CheckProgressStep,
} from '@/components/CheckProgress'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import type { ClassifyFailure } from '@/hooks/use-classify'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'

import {
  CHECK_IDS,
  checkNumber,
  checkState,
  didContinue,
  type CheckId,
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
  /** A result's re-run: its alert alone says why it stopped. */
  isRerun: boolean
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
  state: CheckProgressState,
  context: RowContext,
): Partial<CheckProgressStep> {
  const { t, progress, failure, isRerun } = context
  const reference = t(`progress.reference.${id}`)
  if (failure?.kind === 'provider_refused' && id !== 'facts' && failure.steps.includes(id)) {
    return { detail: t('progress.refused.row') }
  }
  switch (state) {
    case 'error':
      // On a re-run the alert above gives the reason; the row's state word marks where.
      if (isRerun) return {}
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

/** The line under the heading: why the run stopped, or what the checks are doing. None for a
 *  re-run that stopped: its alert says so, in the re-run's words. */
function subtitle(
  t: TFunction,
  progress: ProgressState,
  failure: ClassifyFailure | null,
  isRerun: boolean,
): string | null {
  if (failure === null || isWaitingForDescription(failure, isRerun)) return t('progress.subtitle')
  if (isRerun) return null
  if (failure.kind === 'provider_refused') return t('progress.refused.subtitle')
  return stoppedTitle(t, progress)
}

/** A first run that found the description too thin to start (E13): the screen asks its three
 *  prompts, and the checks wait. A re-run that ends so keeps its earlier result, and says why in
 *  its alert. */
function isWaitingForDescription(failure: ClassifyFailure | null, isRerun: boolean): boolean {
  return failure?.kind === 'needs_description' && !isRerun
}

/** In place of the check list while Klar waits for a description (artboard `ClassifyVague`): no
 *  check has started, and nothing is guessed. */
function WaitingForDescription(): JSX.Element {
  const { t } = useTranslation()
  return (
    <div
      aria-live="polite"
      className="flex flex-col items-center justify-center gap-2.5 rounded-[18px] border-[1.5px] border-dashed border-ink/20 px-7 py-7 text-center"
    >
      <span className="flex size-11 items-center justify-center rounded-[14px] bg-lens-blue/8 text-lens-blue">
        <Icon name="obligations" size={22} />
      </span>
      <p className="m-0 text-body font-semibold text-ink">
        {t('progress.needsDescription.waitingTitle')}
      </p>
      <p className="m-0 max-w-[260px] text-caption font-normal text-slate">
        {t('progress.needsDescription.waitingBody')}
      </p>
    </div>
  )
}

/** The model provider blocked some checks (decision 030): which ones, and that a person must
 *  review the description. The run went on to every check, or ended at a later stopping check
 *  that decided, so nothing here says every check ran. No Try again: the filter would likely
 *  block it again. */
function RefusedAlert({
  failure,
  onSaveForLater,
}: {
  failure: Extract<ClassifyFailure, { kind: 'provider_refused' }>
  onSaveForLater?: () => void
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-card-small px-4 py-3.5 glass-thin">
      <p className="m-0 text-body-small font-semibold text-ink">{t('progress.refused.title')}</p>
      <p className="m-0 text-caption font-normal text-ink-2">{failureReason(t, failure)}</p>
      <p className="m-0 text-caption font-normal text-ink-2">{t('progress.refused.blocked')}</p>
      <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-caption font-normal text-ink-2">
        {failure.steps.map((step) => (
          <li key={step}>{t(`progress.check.${step}`)}</li>
        ))}
      </ul>
      {failure.questions.map((question) => (
        <p key={question} className="m-0 text-caption font-normal text-ink">
          {question}
        </p>
      ))}
      <p className="m-0 text-caption font-normal text-ink-2">{t('progress.refused.body')}</p>
      {onSaveForLater && (
        <div className="flex flex-wrap gap-2.5">
          <Button size="sm" variant="ghost" onClick={onSaveForLater}>
            {t('progress.stopped.saveForLater')}
          </Button>
        </div>
      )}
    </div>
  )
}

export type ProgressPanelProps = {
  progress: ProgressState
  isRunning: boolean
  failure: ClassifyFailure | null
  onTryAgain: () => void
  /** Omitted on a result's re-run, where the result stays and nothing waits to be saved. */
  onSaveForLater?: () => void
  /** A result's re-run (P5b): a failure says the result shown still stands and the answers are
   *  kept, not that nothing is there yet. */
  isRerun?: boolean
}

/** The stopped alert's title and body: on a re-run, that the earlier result stands. */
function stoppedText(t: TFunction, isRerun: boolean): { title: string; body: string | null } {
  if (isRerun) return { title: t('progress.rerun.title'), body: t('progress.rerun.body') }
  return { title: t('progress.stopped.title'), body: t('progress.stopped.body') }
}

/** Why the run stopped, with Try again (and Save for later on the Classify screen). */
function StoppedAlert({
  failure,
  isRerun,
  onTryAgain,
  onSaveForLater,
}: {
  failure: Exclude<ClassifyFailure, { kind: 'provider_refused' }>
  isRerun: boolean
  onTryAgain: () => void
  onSaveForLater?: () => void
}): JSX.Element {
  const { t } = useTranslation()
  const { title, body } = stoppedText(t, isRerun)
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-card-small px-4 py-3.5 glass-thin">
      <p className="m-0 text-body-small font-semibold text-ink">{title}</p>
      <p className="m-0 text-caption font-normal text-ink-2">{failureReason(t, failure)}</p>
      {failure.kind === 'needs_description' && (
        <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-caption font-normal text-ink-2">
          {failure.questions.map((question) => (
            <li key={question.id}>{question.text}</li>
          ))}
        </ul>
      )}
      {body && <p className="m-0 text-caption font-normal text-ink-2">{body}</p>}
      <div className="flex flex-wrap gap-2.5">
        <Button size="sm" onClick={onTryAgain}>
          {t('progress.stopped.tryAgain')}
        </Button>
        {onSaveForLater && (
          <Button size="sm" variant="ghost" onClick={onSaveForLater}>
            {t('progress.stopped.saveForLater')}
          </Button>
        )}
      </div>
    </div>
  )
}

/**
 * The checks beside the description, in the Act's order (artboards `Classify`, `ClassifyError`).
 * When a run stops it says where and why, keeps the description, offers Try again and Save for
 * later, and shows no class. When the description was too thin to start, it waits for one
 * (artboard `ClassifyVague`): the Classify screen asks the prompts.
 */
export function ProgressPanel({
  progress,
  isRunning,
  failure,
  onTryAgain,
  onSaveForLater,
  isRerun = false,
}: ProgressPanelProps): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const rows = progressRows({ t, language, progress, failure, isRerun }, isRunning)
  const line = subtitle(t, progress, failure, isRerun)
  const isWaiting = isWaitingForDescription(failure, isRerun)
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
        {line && <p className="m-0 text-caption font-normal text-slate">{line}</p>}
      </div>
      {failure?.kind === 'provider_refused' && (
        <RefusedAlert failure={failure} onSaveForLater={onSaveForLater} />
      )}
      {failure && failure.kind !== 'provider_refused' && !isWaiting && (
        <StoppedAlert
          failure={failure}
          isRerun={isRerun}
          onTryAgain={onTryAgain}
          onSaveForLater={onSaveForLater}
        />
      )}
      {isWaiting ? <WaitingForDescription /> : <CheckProgress steps={rows} />}
      <p className="m-0 mt-auto rounded-card-small px-3.5 py-3 text-caption font-normal text-ink-2 glass-thin">
        {t('progress.accuracy')}
      </p>
    </GlassPanel>
  )
}
