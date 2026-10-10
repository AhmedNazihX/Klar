import { Link, useNavigate } from '@tanstack/react-router'
import { useCallback, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { ScreenTitle } from '@/components/ScreenTitle'
import { useFollowUpAnswers } from '@/hooks/use-follow-up-answers'
import { useFollowUpRun, type FollowUpRun } from '@/hooks/use-follow-up-run'
import { useOriginalRun } from '@/hooks/use-original-run'

import { isDecidedBan } from './ban'
import { runNumber, saveDraft, type ClassificationRun } from './classification-store'
import { DecidingQuestion } from './DecidingQuestion'
import { DutiesPanel, OutOfScopePanel } from './DutiesPanel'
import { ExportReportButton } from './ExportReportButton'
import { FactsPanel } from './FactsPanel'
import { withAnswers } from './follow-up-answers'
import { FollowUpQuestions } from './FollowUpQuestions'
import { OriginalTextNote } from './OriginalTextNote'
import { ProgressPanel } from './ProgressPanel'
import { ProhibitedSummary } from './ProhibitedSummary'
import { isProviderLayout } from './provider-layout'
import { ProviderAside, ProviderPanels } from './ProviderPanels'
import { RerunChange } from './RerunChange'
import { DraftDocumentsLink, ResultHeader, ViewSwitch, type ResultView } from './ResultHeader'
import { ResultNotice } from './ResultNotice'
import { ResultVerdict } from './ResultVerdict'
import { ReviewerView } from './ReviewerView'
import { StepsPanel } from './StepsPanel'

/** The summary (artboards `Result`, `ResultNeedsInfo`, `ResultRerun`): what the last answer
 *  changed, the class and role, the question that decides an assumed result and the other facts
 *  to confirm (answering runs the checks again, P5b), what to do beside the facts it rests on,
 *  how Klar got there with every step collapsed, and the result's notice. */
function SummaryView({
  run,
  followUp,
  onViewChange,
  onCompare,
}: {
  run: ClassificationRun
  /** The re-run with the answers given here. */
  followUp: FollowUpRun
  onViewChange: (view: ResultView) => void
  /** Opens "Original Act vs amended" in the reviewer view. */
  onCompare: () => void
}): JSX.Element {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { result } = run
  const { deciding, others, answerProps, confirm, tryAgain } = useFollowUpAnswers(run, followUp)
  const isRerunShown = followUp.isRunning || followUp.failure !== null
  // One run action for every question asked, under the last panel (artboard `ResultNeedsInfo`).
  const runCount = others.length + (deciding ? 1 : 0)
  const isBan = isDecidedBan(result)

  function editDescription(): void {
    // The answers go into the text, and the run onto this tool (P6), unless it was never saved.
    const tool = run.saveFailure ? null : { toolId: run.toolId, name: run.name }
    saveDraft(
      { name: run.name ?? '', description: withAnswers(run.description, run.answers) },
      tool,
    )
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

  // What the last answer changed, with its undo (artboard `ResultRerun`).
  const rerunChange = run.previous && (
    <RerunChange
      run={{ ...run, previous: run.previous }}
      onUndo={followUp.undo}
      isUndoing={followUp.isUndoing || followUp.isRunning}
      hasUndoFailed={followUp.hasUndoFailed}
    />
  )
  const rerunProgress = isRerunShown && (
    <ProgressPanel
      progress={followUp.progress}
      isRunning={followUp.isRunning}
      failure={followUp.failure}
      onTryAgain={tryAgain}
      isRerun
    />
  )

  // A decided ban has its own layout (artboard `ResultProhibited`, P21); a fact confirmed there
  // runs the checks again like anywhere else (P5b).
  if (isBan) {
    return (
      <>
        {header}
        {rerunChange}
        <ProhibitedSummary
          run={run}
          note={
            <>
              <OriginalTextNote run={run} onCompare={onCompare} />
              {rerunProgress}
            </>
          }
          onChangeFacts={editDescription}
          onConfirmFact={confirm}
          isBusy={followUp.isRunning}
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
      {rerunChange}
      <ResultVerdict result={result} name={run.name} today={new Date()} />
      <OriginalTextNote run={run} onCompare={onCompare} />
      {deciding && (
        <DecidingQuestion
          question={deciding}
          runCount={others.length === 0 ? runCount : undefined}
          {...answerProps}
        />
      )}
      {others.length > 0 && (
        <FollowUpQuestions questions={others} runCount={runCount} {...answerProps} />
      )}
      {rerunProgress}
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        {result.risk_class === 'out_of_scope' ? (
          <OutOfScopePanel result={result} />
        ) : isProviderLayout(result) ? (
          // A high-risk provider gets its own layout (artboard `ResultProvider`, P23).
          <ProviderPanels result={result} toolId={run.toolId} />
        ) : (
          <DutiesPanel result={result} toolId={run.toolId} />
        )}
        <FactsPanel
          result={result}
          above={isProviderLayout(result) && <ProviderAside result={result} />}
          onChange={editDescription}
          onConfirm={confirm}
          isBusy={followUp.isRunning}
        />
      </div>
      <StepsPanel
        result={result}
        previous={run.previous?.result}
        runNo={runNumber(run)}
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

/** One tool's result, as the summary or the reviewer view. The original-text run and an answer's
 *  re-run live here, above the view switch, so a run started in one view goes on (and keeps its
 *  answer) while the user reads the other. */
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
  const followUp = useFollowUpRun(run)
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
        // Keyed by the run, so answers given on one run don't carry over to the next.
        <SummaryView
          key={runNumber(run)}
          run={run}
          followUp={followUp}
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
