import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, Fact, StepResult } from '@/api'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'
import { StepCard, type StepCardFact, type StepCardQuote } from '@/components/StepCard'
import { useLanguage } from '@/hooks/use-language'

import { provisionName } from './provision-names'
import { citationSource, dutyLabel, rowReferences, stepOutcome } from './result-text'

type HeadingLevel = 2 | 3

function cardFacts(facts: readonly Fact[]): StepCardFact[] {
  // A fact's text is its identity: the engine never lists the same fact twice in a step.
  return [...new Map(facts.map((fact) => [fact.text, fact])).values()].map((fact) => ({
    id: fact.text,
    text: fact.text,
    evidence: fact.evidence,
  }))
}

function StepOutcome({
  step,
  result,
}: {
  step: StepResult
  result: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  if (step.status === 'needs_more_information') return <StatusPill status="needs-info" size="sm" />
  if (step.status === 'legally_ambiguous') return <StatusPill status="ambiguous" size="sm" />
  if (step.step === 'high_risk' && result.risk_class === 'high_risk') {
    return <RiskPill kind="high_risk" />
  }
  return (
    <StatusPill status="decided" size="sm">
      {stepOutcome(t, step, result)}
    </StatusPill>
  )
}

/** One engine step in full: its decision, the facts it rests on with their evidence tags, the
 *  provisions it quotes, and the question it left open. */
export function EngineStepCard({
  name,
  step,
  result,
  headingLevel = 3,
  highlight = false,
}: {
  name: string
  step: StepResult
  result: ClassificationResult
  headingLevel?: HeadingLevel
  highlight?: boolean
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const quotes: StepCardQuote[] = (step.citations ?? []).map((citation) => ({
    id: `${citation.document_id}:${citation.provision_id}`,
    text: citation.quote,
    language: citation.language,
    source: citationSource(t, citation, language),
  }))
  const question = step.missing_fact?.text ?? step.open_question?.question
  return (
    <StepCard
      name={name}
      headingLevel={headingLevel}
      outcome={<StepOutcome step={step} result={result} />}
      reference={rowReferences(step.citations ?? [], language).join(', ')}
      decisionLabel={t('result.steps.decision')}
      decision={step.decision}
      factLabel={t('result.steps.factsUsed')}
      facts={cardFacts(step.facts_used ?? [])}
      quotes={quotes}
      highlight={highlight}
    >
      {question && (
        <p className="m-0 flex flex-col gap-1 text-body-small text-ink">
          <span className="text-slate">{t('result.steps.openQuestion')}</span>
          <span>{question}</span>
        </p>
      )}
    </StepCard>
  )
}

/** The facts Klar read from the description, each with where it came from. */
export function FactsStepCard({
  result,
  headingLevel = 3,
}: {
  result: ClassificationResult
  headingLevel?: HeadingLevel
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <StepCard
      name={t('result.steps.facts')}
      headingLevel={headingLevel}
      reference={t('result.steps.yourDescription')}
      decisionLabel={t('result.steps.decision')}
      factLabel={t('result.steps.factsUsed')}
      facts={cardFacts(result.facts)}
    />
  )
}

/** The duties the role step listed, each with its article. */
export function DutiesStepCard({
  result,
  headingLevel = 3,
}: {
  result: ClassificationResult
  headingLevel?: HeadingLevel
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const obligations = result.obligations ?? []
  return (
    <StepCard
      name={t('result.steps.duties')}
      headingLevel={headingLevel}
      decisionLabel={t('result.steps.decision')}
      decision={
        obligations.length > 0
          ? t('result.steps.dutiesCount', { count: obligations.length })
          : t('result.steps.noDuties')
      }
      factLabel={t('result.steps.factsUsed')}
    >
      {obligations.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-2 p-0 text-body-small text-ink">
          {obligations.map((obligation) => (
            <li
              key={`${obligation.article}:${obligation.duty}`}
              className="flex justify-between gap-4 border-t border-hairline pt-2"
            >
              <span>{dutyLabel(obligation)}</span>
              <span className="shrink-0 text-caption font-normal whitespace-nowrap text-slate">
                {provisionName(obligation.article, language)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </StepCard>
  )
}
