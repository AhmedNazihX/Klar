import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, OpenQuestion } from '@/api'
import { ResultSummary } from '@/components/ResultSummary'
import { riskClassOf } from '@/lib/risk-class'

import { LegacyNotice, StatusPills } from './ResultVerdict'
import { legalReviewLine, useDutiesFrom } from './verdict-lines'

/**
 * The top of a legally ambiguous result (artboard `ResultAmbiguous`): the class Klar assumes,
 * labelled Assumed and Legally ambiguous; that the law leaves one point open, the point itself,
 * and that Klar works from the stricter reading; the date duties would apply from if that reading
 * holds (the route's dates follow the law switch, decision 026 item 11); the legal-review line.
 */
export function AmbiguousVerdict({
  result,
  question,
  today,
}: {
  result: ClassificationResult
  question: OpenQuestion
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const riskClass = riskClassOf(result)
  const duties = useDutiesFrom(result, today)
  return (
    <ResultSummary
      riskClass={riskClass}
      isAmbiguous
      status={<StatusPills result={result} />}
      statement={t('ambiguous.statement')}
      statusLine={question.question}
      dutiesFromLabel={
        riskClass === 'high_risk' ? t('ambiguous.dutiesFromIfHighRisk') : t('result.dutiesFrom')
      }
      dutiesFrom={duties?.date}
      dutiesNote={duties?.note}
      legalReview={legalReviewLine(t, result)}
    >
      <LegacyNotice result={result} />
    </ResultSummary>
  )
}
