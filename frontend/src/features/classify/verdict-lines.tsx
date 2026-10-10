import type { TFunction } from 'i18next'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { LawDate } from '@/components/LawDate'
import { useLanguage } from '@/hooks/use-language'

import { longDate, monthsUntil } from './dates'
import { dutiesDate } from './result-text'

// The lines a result's verdict shares with the ambiguous one (ResultVerdict, AmbiguousVerdict):
// the date duties apply from and the legal-review line.

function monthsLine(t: TFunction, isoDate: string, today: Date, original = false): string {
  const count = monthsUntil(isoDate, today)
  if (count > 0) return t('result.monthsAway', { count })
  return original ? t('result.alreadyAppliesOriginal') : t('result.alreadyApplies')
}

/** The date duties apply from and how far away it is; route dates follow the law version switch. */
export function useDutiesFrom(
  result: ClassificationResult,
  today: Date,
): { date: ReactNode; note: ReactNode } | null {
  const { t } = useTranslation()
  const language = useLanguage()
  const date = dutiesDate(result)
  if (result.risk_class === 'out_of_scope' || date === null) return null
  if (date.kind === 'fixed') {
    return { date: longDate(date.date, language), note: monthsLine(t, date.date, today) }
  }
  return {
    date: (
      <LawDate
        amended={longDate(date.amended, language)}
        original={longDate(date.original, language)}
      />
    ),
    note: (
      <LawDate
        amended={monthsLine(t, date.amended, today)}
        original={monthsLine(t, date.original, today, true)}
      />
    ),
  }
}

export function legalReviewLine(t: TFunction, result: ClassificationResult): string | null {
  if (!result.legal_review) return null
  if (result.status === 'legally_ambiguous') return t('result.legalReview.ambiguous')
  if (result.risk_class === 'high_risk') return t('result.legalReview.high_risk')
  if (result.risk_class === 'prohibited') return t('result.legalReview.prohibited')
  return t('result.legalReview.other')
}
