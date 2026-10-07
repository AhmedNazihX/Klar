import { useId, useState, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, StepName, StepResult } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { STEP_COLUMNS_DE, STEP_COLUMNS_EN, StepRow } from '@/components/StepRow'
import { useLanguage } from '@/hooks/use-language'

import { rowReferences, stepOutcome, SUMMARY_ROWS, type SummaryRowId } from './result-text'
import { DutiesStepCard, EngineStepCard, FactsStepCard } from './StepCards'

type Row = {
  id: SummaryRowId
  name: string
  decision: string
  references: string[]
  card: ReactNode
}

function References({ items }: { items: readonly string[] }): JSX.Element {
  // A reference wraps between references, never inside one.
  return (
    <>
      {items.map((item, index) => (
        <span key={item}>
          <span className="whitespace-nowrap">
            {item}
            {index < items.length - 1 && ','}
          </span>
          {index < items.length - 1 && ' '}
        </span>
      ))}
    </>
  )
}

function findStep(result: ClassificationResult, name: StepName): StepResult | undefined {
  return result.steps.find((step) => step.step === name)
}

/** The rows from the result: each with its one-line outcome, references and expanded card. */
function useRows(result: ClassificationResult): Row[] {
  const { t } = useTranslation()
  const language = useLanguage()
  const obligations = result.obligations ?? []
  const assumed = result.facts.filter((fact) => fact.evidence === 'assumed').length
  return SUMMARY_ROWS.map((id): Row => {
    if (id === 'facts') {
      return {
        id,
        name: t('result.steps.facts'),
        decision: t('result.steps.factsLine', { count: result.facts.length, assumed }),
        references: [t('result.steps.yourDescription')],
        card: <FactsStepCard result={result} />,
      }
    }
    if (id === 'duties') {
      // "Art. 4, 26, 86": the articles, not every paragraph (those are in the to-do list).
      const articles = [...new Set(obligations.map((o) => o.article.split(':').at(1) ?? o.article))]
      return {
        id,
        name: t('result.steps.duties'),
        decision:
          obligations.length > 0
            ? t('result.steps.dutiesCount', { count: obligations.length })
            : t('result.steps.noDuties'),
        references: articles.length > 0 ? [`Art. ${articles.join(', ')}`] : [],
        card: <DutiesStepCard result={result} />,
      }
    }
    const name = id === 'role_obligations' ? t('result.steps.role') : t(`progress.check.${id}`)
    const step = findStep(result, id)
    if (!step) {
      return { id, name, decision: t('result.steps.notChecked'), references: [], card: null }
    }
    return {
      id,
      name,
      decision: stepOutcome(t, step, result),
      references: rowReferences(step.citations ?? [], language),
      card: <EngineStepCard name={name} step={step} result={result} />,
    }
  })
}

/** "How Klar got here": every step collapsed to one line; a row opens to the step in full. */
export function StepsPanel({
  result,
  onExpandAll,
}: {
  result: ClassificationResult
  onExpandAll: () => void
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const rows = useRows(result)
  const [expanded, setExpanded] = useState<ReadonlySet<SummaryRowId>>(new Set())
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex flex-col gap-1.5 px-7 py-5.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 pb-1.5">
        <h2 id={headingId} className="m-0 text-heading-small text-ink">
          {t('result.steps.heading')}
        </h2>
        <button
          type="button"
          onClick={onExpandAll}
          className="cursor-pointer border-0 bg-transparent p-0 text-label text-lens-blue hover:underline"
        >
          {t('result.steps.expandAll')}
        </button>
      </div>
      {rows.map((row) => (
        <StepRow
          key={row.id}
          name={row.name}
          decision={row.decision}
          reference={<References items={row.references} />}
          columns={language === 'de' ? STEP_COLUMNS_DE : STEP_COLUMNS_EN}
          expanded={expanded.has(row.id)}
          onToggle={(isOpen) => {
            setExpanded((previous) => {
              const next = new Set(previous)
              if (isOpen) next.add(row.id)
              else next.delete(row.id)
              return next
            })
          }}
        >
          {row.card ?? <p className="m-0 px-2 text-body-small text-slate">{row.decision}</p>}
        </StepRow>
      ))}
    </GlassPanel>
  )
}
