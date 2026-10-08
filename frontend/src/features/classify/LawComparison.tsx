import type { TFunction } from 'i18next'
import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { VersionDiff, type VersionDiffRow } from '@/components/VersionDiff'
import { useLanguage } from '@/hooks/use-language'
import { useOriginalRun, type OriginalRun } from '@/hooks/use-original-run'

import type { ClassificationRun } from './classification-store'
import { failureReason } from './failure-reason'
import {
  changedSteps,
  comparisonRows,
  type ChangedStep,
  type ComparisonRow,
} from './law-comparison'

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
  }
}

/** What the table says about the Omnibus, one sentence each: whether anything changed, then that
 *  the class didn't when something else did, or that class and role are still to be checked. */
function diffNote(
  t: TFunction,
  rows: readonly ComparisonRow[],
  original: ClassificationResult | undefined,
): string {
  const hasChange = rows.some((row) => row.isKnown && row.original !== row.amended)
  const sentences = [hasChange ? t('diff.note.changed') : t('diff.note.unchanged')]
  const classRow = rows.find((row) => row.id === 'class')
  if (!original) sentences.push(t('diff.note.notChecked'))
  else if (hasChange && classRow?.original === classRow?.amended) {
    sentences.push(t('diff.note.classSame'))
  }
  return sentences.join(' ')
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
 *  or why the last try stopped. */
function CheckOriginal({ original }: { original: OriginalRun }): JSX.Element {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-start gap-2.5">
      <p className="m-0 text-body-small text-ink-2">{t('diff.check.hint')}</p>
      {original.failure && (
        <p role="alert" className="m-0 text-body-small text-ink">
          {t('diff.check.stopped', { reason: failureReason(t, original.failure) })}
        </p>
      )}
      <Button variant="ghost" size="sm" onClick={original.start} disabled={original.isRunning}>
        {original.isRunning
          ? t('diff.check.running')
          : original.failure
            ? t('diff.check.retry')
            : t('diff.check.start')}
      </Button>
    </div>
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
export function LawComparison({ run }: { run: ClassificationRun }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const original = useOriginalRun(run)
  const rows = comparisonRows(t, run.result, original.result, language)
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-3.5 p-5.5"
    >
      <h2 id={headingId} className="m-0 text-heading-panel text-ink">
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
