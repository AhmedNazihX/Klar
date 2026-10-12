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

/** The Art. 5(1) points with a plain-words line (P11, from P21's UI review): every point of the
 *  amended text's list. */
const NO_BREAK_SPACE = '\u00a0'

const PRACTICES = ['a', 'b', 'ba', 'bb', 'c', 'd', 'e', 'f', 'g', 'h'] as const
type Practice = (typeof PRACTICES)[number]

function isPractice(letter: string): letter is Practice {
  return (PRACTICES as readonly string[]).includes(letter)
}

/** A ban point in plain words with its reference ("recognising emotions … (Art. 5(1)(f))"), or
 *  the reference alone for a point without a line. */
function pointLine(t: TFunction, point: string, language: Language): string {
  // No-break spaces: a citation never breaks across lines (localisation.md), even on a phone.
  const reference = provisionName(point, language).replaceAll(' ', NO_BREAK_SPACE)
  const letter = point.split(':').at(-1) ?? ''
  if (!isPractice(letter)) return reference
  return t('prohibited.pointLine', {
    practice: t(`prohibited.practice.${letter}`),
    point: reference,
  })
}

function statement(t: TFunction, result: ClassificationResult, language: Language): string {
  const points = banPoints(result).map((point) => pointLine(t, point, language))
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
      isBan
      status={<StatusPill status="decided" />}
      statement={statement(t, result, language)}
      dutiesFromLabel={t('prohibited.bannedSince')}
      dutiesFrom={longDate(since, language)}
      dutiesNote={timeSince(t, since, today)}
      legalReview={t('prohibited.legalReview')}
    />
  )
}
