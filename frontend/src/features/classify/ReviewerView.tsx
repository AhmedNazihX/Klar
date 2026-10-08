import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Button } from '@/components/Button'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'
import { useLanguage } from '@/hooks/use-language'
import type { OriginalRun } from '@/hooks/use-original-run'

import type { ClassificationRun } from './classification-store'
import { LawComparison } from './LawComparison'
import { provisionName } from './provision-names'
import { ResultHeader, ViewSwitch, type ResultView } from './ResultHeader'
import { ResultNotice } from './ResultNotice'
import { decidingStep, statusPill, SUMMARY_ROWS } from './result-text'
import { DutiesStepCard, EngineStepCard, FactsStepCard } from './StepCards'

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

function ResultPills({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  return (
    <div className="flex flex-wrap items-center gap-2">
      <RiskPill kind={result.risk_class} />
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
 * (VersionDiff, P10); the thread (P7) joins it.
 */
export function ReviewerView({
  run,
  original,
  shouldFocusComparison = false,
  onComparisonFocused,
  onViewChange,
}: {
  run: ClassificationRun
  /** The original-text run the comparison shows (the result screen owns it). */
  original: OriginalRun
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
          </>
        }
      />
      <ResultPills result={result} />
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        <div className="flex min-w-0 flex-1 flex-col gap-5">
          {SUMMARY_ROWS.map((id) => {
            if (id === 'facts') return <FactsStepCard key={id} result={result} headingLevel={2} />
            if (id === 'duties')
              return <DutiesStepCard key={id} result={result} headingLevel={2} hasOriginalNote />
            const step = result.steps.find((candidate) => candidate.step === id)
            if (!step) return null
            const name =
              id === 'role_obligations' ? t('result.steps.role') : t(`progress.check.${id}`)
            return (
              <EngineStepCard
                key={id}
                name={name}
                step={step}
                result={result}
                headingLevel={2}
                highlight={deciding === id}
              />
            )
          })}
        </div>
        {/* The comparison needs the amended result as its one side: a result run under the
            original text has nothing to compare against. */}
        {result.law_version === 'amended' && (
          <div className="flex min-w-0 flex-col gap-4 xl:w-[380px] xl:shrink-0">
            <LawComparison
              run={run}
              original={original}
              shouldTakeFocus={shouldFocusComparison}
              onFocused={onComparisonFocused}
            />
          </div>
        )}
      </div>
      <ResultNotice result={result} isStored={run.isStored} />
    </>
  )
}
