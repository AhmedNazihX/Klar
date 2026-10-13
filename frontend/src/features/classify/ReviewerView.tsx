import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, StepName } from '@/api'
import { Button } from '@/components/Button'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'
import { useLanguage } from '@/hooks/use-language'
import type { OriginalRun } from '@/hooks/use-original-run'

import { ResultQuestions } from '@/features/ask/ResultQuestions'
import { SourceDocuments } from '@/features/ask/SourceDocuments'
import type { QaThread } from '@/hooks/use-qa-thread'

import { isUncheckedOnBan } from './ban'
import type { ClassificationRun } from './classification-store'
import { ExportReportButton } from './ExportReportButton'
import { LawComparison } from './LawComparison'
import { provisionName } from './provision-names'
import { ResultHeader, ViewSwitch, type ResultView } from './ResultHeader'
import { ResultNotice } from './ResultNotice'
import { decidingStep, statusPill, SUMMARY_ROWS, type SummaryRowId } from './result-text'
import { DutiesStepCard, EngineStepCard, FactsStepCard, NotCheckedStepCard } from './StepCards'
import { riskClassOf } from '@/lib/risk-class'

const JSON_INDENT = 2

/** Saves the result as the API returned it, for a reviewer or a lawyer. */
function exportJson(run: ClassificationRun): void {
  const blob = new Blob([JSON.stringify(run.result, null, JSON_INDENT)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${run.toolId}.json`
  link.click()
  URL.revokeObjectURL(url)
}

/** One row of the reviewer view in full. On a decided ban the steps after Art. 5 never ran, and
 *  their cards say so, as the summary's rows do (artboard `ResultProhibited`). */
function ReviewerStep({
  id,
  result,
  deciding,
}: {
  id: SummaryRowId
  result: ClassificationResult
  deciding: StepName | null
}): JSX.Element | null {
  const { t } = useTranslation()
  if (id === 'facts') return <FactsStepCard result={result} headingLevel={2} />
  const name =
    id === 'duties'
      ? t('result.steps.duties')
      : id === 'role_obligations'
        ? t('result.steps.role')
        : t(`progress.check.${id}`)
  if (isUncheckedOnBan(result, id)) {
    return <NotCheckedStepCard name={name} reason={t('prohibited.notChecked')} headingLevel={2} />
  }
  if (id === 'duties') return <DutiesStepCard result={result} headingLevel={2} hasOriginalNote />
  const step = result.steps.find((candidate) => candidate.step === id)
  // Without a ban, a step is missing only from a result stored without it: nothing to show.
  if (!step) return null
  return (
    <EngineStepCard
      name={name}
      step={step}
      result={result}
      headingLevel={2}
      highlight={deciding === id}
    />
  )
}

function ResultPills({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  return (
    <div className="flex flex-wrap items-center gap-2">
      <RiskPill kind={riskClassOf(result)} />
      {result.role && (
        <StatusPill status="decided">{t(`result.roleName.${result.role}`)}</StatusPill>
      )}
      {result.annex_point && (
        <StatusPill status="decided">{provisionName(result.annex_point, language)}</StatusPill>
      )}
      <StatusPill status={statusPill(result.status)} />
    </div>
  )
}

/**
 * The reviewer view (artboard `Reviewer`): every step expanded, in the Act's order, with its
 * decision, the facts it rests on with their evidence tags, and the quoted provisions. The step
 * that decided a High-risk result is highlighted. Beside the steps, "Original Act vs amended"
 * (VersionDiff, P10), under it "Questions about this result" (P7), then the texts the result quotes
 * ("Texts used", with their status).
 */
export function ReviewerView({
  run,
  original,
  questions,
  shouldFocusComparison = false,
  onComparisonFocused,
  onViewChange,
}: {
  run: ClassificationRun
  /** The original-text run the comparison shows (the result screen owns it). */
  original: OriginalRun
  /** Questions about this result (the result screen holds them, above the view switch). */
  questions: QaThread
  /** Whether the comparison takes the focus as the view opens. */
  shouldFocusComparison?: boolean
  /** Called once the comparison has taken that focus. */
  onComparisonFocused?: () => void
  onViewChange: (view: ResultView) => void
}): JSX.Element {
  const { t } = useTranslation()
  const { result } = run
  const deciding = result.risk_class === 'high_risk' ? decidingStep(result) : null
  return (
    <>
      <ResultHeader
        name={run.name}
        result={result}
        actions={
          <>
            <ViewSwitch view="reviewer" onViewChange={onViewChange} />
            <Button
              variant="ghost"
              onClick={() => {
                exportJson(run)
              }}
            >
              {t('result.reviewer.exportJson')}
            </Button>
            <ExportReportButton run={run} />
          </>
        }
      />
      <ResultPills result={result} />
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        <div className="flex min-w-0 flex-1 flex-col gap-5">
          {SUMMARY_ROWS.map((id) => (
            <ReviewerStep key={id} id={id} result={result} deciding={deciding} />
          ))}
        </div>
        <div className="flex min-w-0 flex-col gap-4 xl:w-[380px] xl:shrink-0">
          {/* The comparison needs the amended result as its one side: a result run under the
              original text has nothing to compare against. */}
          {result.law_version === 'amended' && (
            <LawComparison
              run={run}
              original={original}
              shouldTakeFocus={shouldFocusComparison}
              onFocused={onComparisonFocused}
            />
          )}
          <ResultQuestions qa={questions} />
          <SourceDocuments
            heading={t('ask.sources.textsUsed')}
            lawVersion={result.law_version}
            usedBy={result}
          />
        </div>
      </div>
      <ResultNotice result={result} isStored={run.isStored} />
    </>
  )
}
