import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { ChangeBanner } from '@/components/ChangeBanner'
import { GlassPanel } from '@/components/GlassPanel'
import { RiskPill } from '@/components/RiskPill'
import { useLanguage } from '@/hooks/use-language'
import { riskClassOf } from '@/lib/risk-class'

import { runNumber, type ClassificationRun } from './classification-store'
import { classLabel, dutiesLabel, hasResultChanged, needsLabel, newAnswers } from './rerun-change'

function ClassPill({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  return <RiskPill kind={riskClassOf(result)} label={classLabel(t, result)} />
}

/** "What changed in your lists": the tool's line in the Inventory, Obligations and "needs you"
 *  lists, before and after the answer. */
function ListChanges({
  before,
  after,
}: {
  before: ClassificationResult
  after: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const rows = [
    {
      id: 'inventory',
      name: t('nav.inventory'),
      before: <ClassPill result={before} />,
      after: <ClassPill result={after} />,
    },
    {
      id: 'obligations',
      name: t('nav.obligations'),
      before: dutiesLabel(t, before),
      after: dutiesLabel(t, after),
    },
    {
      id: 'needs',
      name: t('followUp.lists.needs'),
      before: needsLabel(t, before, language),
      after: needsLabel(t, after, language),
    },
  ]
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-2 px-6 py-5">
      <h2 id={headingId} className="m-0 text-heading-small text-ink">
        {t('followUp.lists.heading')}
      </h2>
      <dl className="m-0 flex flex-col">
        {rows.map((row) => (
          <div
            key={row.id}
            className="grid gap-1 border-t border-hairline py-2.5 text-body-small md:grid-cols-[160px_minmax(0,1fr)]"
          >
            <dt className="font-semibold text-ink">{row.name}</dt>
            <dd className="m-0 flex flex-wrap items-center gap-2 text-ink-2">
              <span className="text-slate">{row.before}</span>
              <span aria-hidden="true" className="text-slate">
                →
              </span>
              <span className="sr-only">{t('followUp.banner.changeLabel')}</span>
              <span className="text-ink">{row.after}</span>
            </dd>
          </div>
        ))}
      </dl>
    </GlassPanel>
  )
}

/**
 * After an answer (artboard `ResultRerun`): what the re-run changed, the run's number and Undo
 * answer, then the tool's lines in the user's lists before and after. Shown only on a run an
 * answer made, while the run before it is known.
 */
export function RerunChange({
  run,
  onUndo,
  isUndoing,
  hasUndoFailed,
}: {
  run: ClassificationRun & { previous: NonNullable<ClassificationRun['previous']> }
  onUndo: () => void
  isUndoing: boolean
  hasUndoFailed: boolean
}): JSX.Element {
  const { t } = useTranslation()
  const { previous, result } = run
  const said = newAnswers(run.answers, previous.answers)
  const number = runNumber(run)
  return (
    <>
      <ChangeBanner
        title={
          hasResultChanged(previous.result, result)
            ? t('followUp.banner.changed')
            : t('followUp.banner.unchanged')
        }
        before={<ClassPill result={previous.result} />}
        after={<ClassPill result={result} />}
        changeLabel={t('followUp.banner.changeLabel')}
        runLabel={t('followUp.banner.run', { number, total: number })}
        onUndo={onUndo}
        undoLabel={t('followUp.banner.undo')}
        isUndoing={isUndoing}
      >
        <p className="m-0 text-body-small text-ink-2">{t('followUp.banner.body')}</p>
        {said.length > 0 && (
          <ul className="m-0 flex list-none flex-col gap-1 p-0 text-body-small text-ink">
            {said.map((text) => (
              <li key={text}>{t('followUp.banner.youSaid', { answer: text })}</li>
            ))}
          </ul>
        )}
        {hasUndoFailed && (
          <p role="alert" className="m-0 text-body-small text-ink">
            {t('followUp.banner.undoFailed')}
          </p>
        )}
      </ChangeBanner>
      <ListChanges before={previous.result} after={result} />
    </>
  )
}
