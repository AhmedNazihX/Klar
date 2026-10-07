import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Button } from '@/components/Button'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'
import { useLanguage } from '@/hooks/use-language'

import type { ClassificationRun } from './classification-store'
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
 * that decided a High-risk result is highlighted. VersionDiff (P10) and the thread (P7) join it.
 */
export function ReviewerView({
  run,
  onViewChange,
}: {
  run: ClassificationRun
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
      {SUMMARY_ROWS.map((id) => {
        if (id === 'facts') return <FactsStepCard key={id} result={result} headingLevel={2} />
        if (id === 'duties') return <DutiesStepCard key={id} result={result} headingLevel={2} />
        const step = result.steps.find((candidate) => candidate.step === id)
        if (!step) return null
        const name = id === 'role_obligations' ? t('result.steps.role') : t(`progress.check.${id}`)
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
      <ResultNotice result={result} />
    </>
  )
}
