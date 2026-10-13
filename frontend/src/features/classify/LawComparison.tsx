import type { TFunction } from 'i18next'
import { useEffect, useId, useRef, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { VersionDiff, type VersionDiffRow } from '@/components/VersionDiff'
import { useLanguage } from '@/hooks/use-language'
import type { OriginalRun } from '@/hooks/use-original-run'

import type { ClassificationRun } from './classification-store'
import { failureReason } from './failure-reason'
import {
  changedSteps,
  comparisonRows,
  type ChangedStep,
  type ComparisonRow,
} from './law-comparison'

/** A date and an Annex point stay whole on one line; a class or a role wraps between words. */
const ROW_KINDS: Record<ComparisonRow['id'], VersionDiffRow['kind']> = {
  class: 'text',
  basis: 'reference',
  role: 'text',
  dutiesFrom: 'date',
}

function diffRow(t: TFunction, row: ComparisonRow): VersionDiffRow {
  return {
    id: row.id,
    label: t(`diff.row.${row.id}`),
    before: row.isKnown ? (
      row.original
    ) : (
      <span className="font-normal text-slate">{row.original}</span>
    ),
    after: row.amended,
    isChanged: row.isKnown && row.original !== row.amended,
    kind: ROW_KINDS[row.id],
  }
}

/** What the table says about the Omnibus, one sentence each. Before the original text is checked
 *  only the date is known: whether the Omnibus moved it, then that class and role aren't checked
 *  yet. After: whether anything changed, then that the class didn't when something else did. */
function diffNote(
  t: TFunction,
  rows: readonly ComparisonRow[],
  original: ClassificationResult | undefined,
): string {
  const hasChange = rows.some((row) => row.isKnown && row.original !== row.amended)
  if (!original) {
    const notChecked = t('diff.note.notChecked')
    return hasChange ? `${t('diff.note.dateChanged')} ${notChecked}` : notChecked
  }
  const classRow = rows.find((row) => row.id === 'class')
  if (!hasChange) return t('diff.note.unchanged')
  if (classRow?.original !== classRow?.amended) return t('diff.note.changed')
  return `${t('diff.note.changed')} ${t('diff.note.classSame')}`
}

/** The steps whose outcome the Omnibus changed, each with the changed provisions it rests on. */
function ChangedSteps({ steps }: { steps: readonly ChangedStep[] }): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  if (steps.length === 0) {
    return <p className="m-0 text-body-small text-ink-2">{t('diff.steps.none')}</p>
  }
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2.5">
      <h3 id={headingId} className="m-0 text-label font-semibold text-ink">
        {t('diff.steps.heading')}
      </h3>
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {steps.map((changed) => (
          <li
            key={changed.step}
            className="flex flex-col gap-1 rounded-card-small px-4 py-3 text-body-small glass-thin"
          >
            <span className="font-semibold text-ink">
              {changed.step === 'role_obligations'
                ? t('result.steps.role')
                : t(`progress.check.${changed.step}`)}
            </span>
            <span className="text-ink-2">
              {t('diff.steps.change', { original: changed.original, amended: changed.amended })}
            </span>
            {changed.omnibusProvisions.length > 0 && (
              <span className="text-slate">
                {t('diff.steps.why', { provisions: changed.omnibusProvisions.join(', ') })}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Before the original text is checked: the button that runs it (a paid run, so only on a click),
 *  or why the last try stopped. A run the model provider's filter refused isn't offered again: the
 *  same text would most likely be refused again (decision 030), as on the Classify screen. Its
 *  alert alone says so, and that the amended result stands; nothing offers to run it again. */
function CheckOriginal({ original }: { original: OriginalRun }): JSX.Element {
  const { t } = useTranslation()
  if (original.failure?.kind === 'provider_refused') {
    return (
      <p role="alert" className="m-0 text-body-small text-ink">
        {t('diff.check.refused')}
      </p>
    )
  }
  return (
    <div className="flex flex-col items-start gap-2.5">
      <p className="m-0 text-body-small text-ink-2">{t('diff.check.hint')}</p>
      {original.failure && (
        <p role="alert" className="m-0 text-body-small text-ink">
          {t('diff.check.stopped', { reason: failureReason(t, original.failure) })}
        </p>
      )}
      <RunOriginalButton original={original} />
    </div>
  )
}

function RunOriginalButton({ original }: { original: OriginalRun }): JSX.Element {
  const { t } = useTranslation()
  return (
    <Button variant="ghost" size="sm" onClick={original.start} disabled={original.isRunning}>
      {original.isRunning
        ? t('diff.check.running')
        : original.failure
          ? t('diff.check.retry')
          : t('diff.check.start')}
    </Button>
  )
}

/**
 * "Original Act vs amended" in the reviewer view (artboard `Reviewer`, components.md ›
 * VersionDiff): the class, role and date duties apply from under each text, with the Omnibus
 * named in the note. The original side comes from the engine's own original-text run, which the
 * user starts here; until then only the date is known. Once it ran, the steps that changed are
 * listed with the provisions the Omnibus changed, and the duties' notice: the original text's
 * duties aren't modelled (decision 020).
 */
export function LawComparison({
  run,
  original,
  shouldTakeFocus = false,
  onFocused,
}: {
  run: ClassificationRun
  /** The original-text run, owned by the result screen so that it outlives a view change. */
  original: OriginalRun
  /** Whether the panel takes the focus when it shows (opened from the summary's "Compare"). */
  shouldTakeFocus?: boolean
  /** Called once the panel has taken the focus, so the screen can drop the request. */
  onFocused?: () => void
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  // Focus is outside React: move it once, when the panel opens from the summary.
  useEffect(() => {
    if (!shouldTakeFocus) return
    headingRef.current?.focus()
    onFocused?.()
  }, [shouldTakeFocus, onFocused])
  const rows = comparisonRows(t, run.result, original.result, language)
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-3.5 p-5.5"
    >
      <h2
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        className="m-0 text-heading-panel text-ink outline-none"
      >
        {t('diff.heading')}
      </h2>
      <VersionDiff
        rows={rows.map((row) => diffRow(t, row))}
        note={diffNote(t, rows, original.result)}
      />
      <div aria-live="polite" className="flex flex-col gap-3.5">
        {original.result ? (
          <>
            <ChangedSteps steps={changedSteps(t, run.result, original.result, language)} />
            <p className="m-0 text-caption font-normal text-ink-2">{t('diff.dutiesNotModelled')}</p>
          </>
        ) : (
          <CheckOriginal original={original} />
        )}
      </div>
    </GlassPanel>
  )
}
