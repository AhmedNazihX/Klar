import type { TFunction } from 'i18next'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { ResultSummary } from '@/components/ResultSummary'
import { StatusPill } from '@/components/StatusPill'
import { useLanguage } from '@/hooks/use-language'
import { LANGUAGE_LOCALES, type Language } from '@/i18n'

import { bannedSince, banPoints } from './ban'
import { longDate, monthsSince } from './dates'
import { provisionName } from './provision-names'

function statement(t: TFunction, result: ClassificationResult, language: Language): string {
  const points = banPoints(result).map((point) => provisionName(point, language))
  if (points.length === 0) return t('prohibited.statementPlain')
  const list = new Intl.ListFormat(LANGUAGE_LOCALES[language], { type: 'conjunction' })
  return t('prohibited.statement', { points: list.format(points) })
}

function timeSince(t: TFunction, isoDate: string, today: Date): string {
  const count = monthsSince(isoDate, today)
  return count > 0 ? t('prohibited.monthsAgo', { count }) : t('prohibited.underAMonth')
}

/** The top of a prohibited result (artboard `ResultProhibited`): the class, decided; the points
 *  that ban it, where the checks stopped; the date it has been banned since and how long ago
 *  that was; and the strong legal-advice line (decision 026 item 12). */
export function ProhibitedVerdict({
  result,
  today,
}: {
  result: ClassificationResult
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const since = bannedSince(banPoints(result))
  return (
    <ResultSummary
      riskClass="prohibited"
      status={<StatusPill status="decided" />}
      statement={statement(t, result, language)}
      dutiesFromLabel={t('prohibited.bannedSince')}
      dutiesFrom={longDate(since, language)}
      dutiesNote={timeSince(t, since, today)}
      legalReview={t('prohibited.legalReview')}
    />
  )
}
