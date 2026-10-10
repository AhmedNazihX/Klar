import { Link, useNavigate } from '@tanstack/react-router'
import { useCallback, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { ScreenTitle } from '@/components/ScreenTitle'
import { useOriginalRun } from '@/hooks/use-original-run'

import { isDecidedBan } from './ban'
import { saveDraft, type ClassificationRun } from './classification-store'
import { DecidingQuestion } from './DecidingQuestion'
import { DutiesPanel, OutOfScopePanel } from './DutiesPanel'
import { ExportReportButton } from './ExportReportButton'
import { FactsPanel } from './FactsPanel'
import { OriginalTextNote } from './OriginalTextNote'
import { ProhibitedSummary } from './ProhibitedSummary'
import { DraftDocumentsLink, ResultHeader, ViewSwitch, type ResultView } from './ResultHeader'
import { ResultNotice } from './ResultNotice'
import { ResultVerdict } from './ResultVerdict'
import { pausedStep } from './result-text'
import { ReviewerView } from './ReviewerView'
import { StepsPanel } from './StepsPanel'

/** The summary (artboards `Result`, `ResultNeedsInfo`): the class and role, the question that
 *  decides an assumed result, what to do beside the facts it rests on, how Klar got there with
 *  every step collapsed, and the result's notice. */
function SummaryView({
  run,
  onViewChange,
  onCompare,
}: {
  run: ClassificationRun
  onViewChange: (view: ResultView) => void
  /** Opens "Original Act vs amended" in the reviewer view. */
  onCompare: () => void
}): JSX.Element {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { result } = run
  const question = result.status === 'needs_more_information' ? pausedStep(result) : null
  const isBan = isDecidedBan(result)

  function editDescription(): void {
    saveDraft({ name: run.name ?? '', description: run.description })
    void navigate({ to: '/app/classify' })
  }

  const header = (
    <ResultHeader
      name={run.name}
      result={result}
      actions={
        <>
          <ViewSwitch view="summary" onViewChange={onViewChange} />
          <Button variant="ghost" onClick={editDescription}>
            {t('result.editDescription')}
          </Button>
          {/* There's no route to comply with a ban, so there are no documents to draft. */}
          {!isBan && <DraftDocumentsLink toolId={run.toolId} />}
          <ExportReportButton run={run} />
        </>
      }
    />
  )

  // A decided ban has its own layout (artboard `ResultProhibited`, P21).
  if (isBan) {
    return (
      <>
        {header}
        <ProhibitedSummary
          run={run}
          note={<OriginalTextNote run={run} onCompare={onCompare} />}
          onChangeFacts={editDescription}
          onExpandAll={() => {
            onViewChange('reviewer')
          }}
        />
        <ResultNotice result={result} isStored={run.isStored} />
      </>
    )
  }

  return (
    <>
      {header}
      <ResultVerdict result={result} today={new Date()} />
      <OriginalTextNote run={run} onCompare={onCompare} />
      {question && <DecidingQuestion question={question.missing_fact} />}
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        {result.risk_class === 'out_of_scope' ? (
          <OutOfScopePanel result={result} />
        ) : (
          <DutiesPanel result={result} toolId={run.toolId} />
        )}
        <FactsPanel result={result} onChange={editDescription} />
      </div>
      <StepsPanel
        result={result}
        onExpandAll={() => {
          onViewChange('reviewer')
        }}
      />
      <ResultNotice result={result} isStored={run.isStored} />
    </>
  )
}

/** A fresh run the inventory couldn't take: it shows here, but only until the tab goes. */
function NotSavedNote({
  failure,
}: {
  failure: NonNullable<ClassificationRun['saveFailure']>
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <p
      role="alert"
      data-failure={failure}
      className="m-0 rounded-card-small px-4 py-3 text-body-small text-ink glass-thin"
    >
      {failure === 'storage-full' ? t('result.notSaved.storageFull') : t('result.notSaved.failed')}
    </p>
  )
}

/** A tool id the user has no tool for (not theirs, or deleted). */
export function ResultNotFound(): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <ScreenTitle>{t('screen.result')}</ScreenTitle>
      <GlassPanel className="flex flex-col items-start gap-4">
        <p className="m-0 text-body text-slate">{t('result.notFound.body')}</p>
        <Link to="/app/classify" className={buttonVariants()}>
          {t('result.notFound.action')}
        </Link>
      </GlassPanel>
    </>
  )
}

/** One tool's result, as the summary or the reviewer view. The original-text run lives here, above
 *  the view switch, so a run started in the reviewer view goes on (and keeps its answer) while the
 *  user reads the summary. */
export function ResultScreen({
  run,
  view,
  onViewChange,
}: {
  run: ClassificationRun
  view: ResultView
  onViewChange: (view: ResultView) => void
}): JSX.Element {
  const original = useOriginalRun(run)
  // Set only by the summary's "Compare the two texts", so the comparison then takes the focus.
  const [shouldFocusComparison, setShouldFocusComparison] = useState(false)

  // Once the comparison has the focus the request is spent: a later arrival in the reviewer view
  // (browser back or forward, the view switch) doesn't pull the focus again.
  const dropFocusRequest = useCallback(() => {
    setShouldFocusComparison(false)
  }, [])

  function changeView(next: ResultView): void {
    setShouldFocusComparison(false)
    onViewChange(next)
  }

  // A fragment, so the note and the view's panels stay the screen's direct children (load motion).
  return (
    <>
      {run.saveFailure && <NotSavedNote failure={run.saveFailure} />}
      {view === 'reviewer' ? (
        <ReviewerView
          run={run}
          original={original}
          shouldFocusComparison={shouldFocusComparison}
          onComparisonFocused={dropFocusRequest}
          onViewChange={changeView}
        />
      ) : (
        <SummaryView
          run={run}
          onViewChange={changeView}
          onCompare={() => {
            setShouldFocusComparison(true)
            onViewChange('reviewer')
          }}
        />
      )}
    </>
  )
}
