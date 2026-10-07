import { Link, useNavigate } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { ScreenTitle } from '@/components/ScreenTitle'

import { saveDraft, type ClassificationRun } from './classification-store'
import { DecidingQuestion } from './DecidingQuestion'
import { DutiesPanel, OutOfScopePanel } from './DutiesPanel'
import { FactsPanel } from './FactsPanel'
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
}: {
  run: ClassificationRun
  onViewChange: (view: ResultView) => void
}): JSX.Element {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { result } = run
  const question = result.status === 'needs_more_information' ? pausedStep(result) : null

  function editDescription(): void {
    saveDraft({ name: run.name, description: run.description })
    void navigate({ to: '/app/classify' })
  }

  return (
    <>
      <ResultHeader
        name={run.name}
        result={result}
        actions={
          <>
            <ViewSwitch view="summary" onViewChange={onViewChange} />
            <Button variant="ghost" onClick={editDescription}>
              {t('result.editDescription')}
            </Button>
            <DraftDocumentsLink />
          </>
        }
      />
      <ResultVerdict result={result} today={new Date()} />
      {question && <DecidingQuestion question={question.missing_fact} />}
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        {result.risk_class === 'out_of_scope' ? (
          <OutOfScopePanel result={result} />
        ) : (
          <DutiesPanel result={result} />
        )}
        <FactsPanel result={result} onChange={editDescription} />
      </div>
      <StepsPanel
        result={result}
        onExpandAll={() => {
          onViewChange('reviewer')
        }}
      />
      <ResultNotice result={result} />
    </>
  )
}

/** A tool this session has no result for. */
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

/** One tool's result, as the summary or the reviewer view. */
export function ResultScreen({
  run,
  view,
  onViewChange,
}: {
  run: ClassificationRun
  view: ResultView
  onViewChange: (view: ResultView) => void
}): JSX.Element {
  return view === 'reviewer' ? (
    <ReviewerView run={run} onViewChange={onViewChange} />
  ) : (
    <SummaryView run={run} onViewChange={onViewChange} />
  )
}
