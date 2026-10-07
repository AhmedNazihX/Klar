import type { TFunction } from 'i18next'
import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, LegacyStatus, Role } from '@/api'
import { LawDate } from '@/components/LawDate'
import { ResultSummary } from '@/components/ResultSummary'
import { StatusPill } from '@/components/StatusPill'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'

import { checkNumber } from './classify-progress'
import { longDate, monthsUntil, PUBLIC_AUTHORITY_DEADLINE, routeOfPoint } from './dates'
import { amendedRouteDate, basisSentence, dutiesDate, pausedStep } from './result-text'

/** The roles that supply the system: Art. 111(2) counts per copy supplied (decision 022). */
const SUPPLIER_ROLES: readonly Role[] = ['provider', 'importer', 'distributor']

function StatusPills({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  if (result.status === 'decided') return <StatusPill status="decided" />
  return (
    <>
      <StatusPill status="decided">{t('result.assumed')}</StatusPill>
      <StatusPill status={result.status === 'legally_ambiguous' ? 'ambiguous' : 'needs-info'} />
    </>
  )
}

function monthsLine(t: TFunction, isoDate: string, today: Date, original = false): string {
  const count = monthsUntil(isoDate, today)
  if (count > 0) return t('result.monthsAway', { count })
  return original ? t('result.alreadyAppliesOriginal') : t('result.alreadyApplies')
}

/** The date duties apply from and how far away it is; route dates follow the law version switch. */
function useDutiesFrom(
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

function legalReviewLine(t: TFunction, result: ClassificationResult): string | null {
  if (!result.legal_review) return null
  if (result.status === 'legally_ambiguous') return t('result.legalReview.ambiguous')
  if (result.risk_class === 'high_risk') return t('result.legalReview.high_risk')
  if (result.risk_class === 'prohibited') return t('result.legalReview.prohibited')
  return t('result.legalReview.other')
}

function pausedLine(t: TFunction, result: ClassificationResult): string | null {
  if (result.status !== 'needs_more_information') return null
  const step = pausedStep(result)
  if (!step) return null
  const number = checkNumber(step.step)
  return number === null ? t('result.pausedAtDuties') : t('result.paused', { number })
}

/** The Art. 111(2) sentences for the markings the duties carry, plus the per-copy caveat for a
 *  role that supplies the system (decision 026 item 24). The route's date comes from the duties
 *  the engine dated; when Art. 111(2) moved every one of them to 2030 (a provider or deployer of
 *  a system for public authorities), the result has no route date and the sentences go without. */
function legacySentences(t: TFunction, result: ClassificationResult, language: Language): string[] {
  const statuses = new Set(
    (result.obligations ?? [])
      .map((obligation) => obligation.legacy)
      .filter((status): status is LegacyStatus => Boolean(status)),
  )
  if (statuses.size === 0) return []
  const routeDate = amendedRouteDate(result, routeOfPoint(result.annex_point) ?? 'annex_iii')
  const date = routeDate && longDate(routeDate, language)
  const deadline = longDate(PUBLIC_AUTHORITY_DEADLINE, language)
  // Without a route date no duty is merely unchanged-marked: they are all public-authority ones.
  const marked = date
    ? [...statuses].map((status) => t(`result.legacy.${status}`, { date, deadline }))
    : [t('result.legacy.publicAuthorityUndated', { deadline })]
  const roles = [result.role, result.also_role]
  const supplies = roles.some((role) => role && SUPPLIER_ROLES.includes(role))
  if (!supplies) return marked
  const perCopy = date
    ? t('result.legacy.perProduct', { date })
    : t('result.legacy.perProductUndated')
  return [...marked, perCopy]
}

/** The top of the result (ResultSummary): the class and its status, who you are and why, the
 *  date duties apply from, the Art. 111(2) notice and the legal-review line. */
export function ResultVerdict({
  result,
  today,
}: {
  result: ClassificationResult
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const duties = useDutiesFrom(result, today)
  const legacy = legacySentences(t, result, language)
  return (
    <ResultSummary
      riskClass={result.risk_class}
      status={<StatusPills result={result} />}
      statement={
        <>
          {result.role && <span>{t(`result.role.${result.role}`)} </span>}
          {result.also_role && <span>{t(`result.alsoRole.${result.also_role}`)} </span>}
          <span>{basisSentence(t, result, language)}</span>
        </>
      }
      statusLine={pausedLine(t, result)}
      dutiesFromLabel={t('result.dutiesFrom')}
      dutiesFrom={duties?.date}
      dutiesNote={duties?.note}
      legalReview={legalReviewLine(t, result)}
    >
      {legacy.length > 0 && (
        <div role="note" className="flex flex-col gap-1.5 rounded-card-small px-4 py-3 glass-thin">
          {legacy.map((sentence) => (
            <p key={sentence} className="m-0 text-label font-normal text-ink-2">
              {sentence}
            </p>
          ))}
        </div>
      )}
    </ResultSummary>
  )
}
