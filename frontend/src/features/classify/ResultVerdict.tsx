import type { TFunction } from 'i18next'
import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, LegacyStatus, RiskClass, Role } from '@/api'
import { LawDate } from '@/components/LawDate'
import { ResultSummary } from '@/components/ResultSummary'
import { StatusPill } from '@/components/StatusPill'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'

import { checkNumber } from './classify-progress'
import { longDate, monthsUntil, PUBLIC_AUTHORITY_DEADLINE, routeOfPoint } from './dates'
import { isProviderLayout, providerReason } from './provider-layout'
import { amendedRouteDate, basisSentence, dutiesDate, pausedStep, statusPill } from './result-text'
import { riskClassOf } from '@/lib/risk-class'

/** The roles that supply the system: Art. 111(2) counts per copy supplied (decision 022). */
const SUPPLIER_ROLES: readonly Role[] = ['provider', 'importer', 'distributor']

function StatusPills({ result }: { result: ClassificationResult }): JSX.Element {
  const { t } = useTranslation()
  // The provider layout names the role in a pill too (artboard `ResultProvider`).
  const role = isProviderLayout(result) && (
    <StatusPill status="decided">{t('result.roleName.provider')}</StatusPill>
  )
  if (result.status === 'decided') {
    return (
      <>
        <StatusPill status="decided" />
        {role}
      </>
    )
  }
  return (
    <>
      <StatusPill status="decided">{t('result.assumed')}</StatusPill>
      <StatusPill status={statusPill(result.status)} />
      {role}
    </>
  )
}

/** Who you are: the role line, which on the provider layout says why you're the provider (an
 *  Art. 25(1) switch keeps the engine's reason, which the reviewer view shows with its citation). */
function roleLine(t: TFunction, result: ClassificationResult): string | null {
  if (!result.role) return null
  if (!isProviderLayout(result)) return t(`result.role.${result.role}`)
  const reason = providerReason(result)
  if (reason === 'own' || reason === 'gpai') return t(`result.provider.reason.${reason}`)
  return t('result.role.provider')
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

/** The class as the paused lines name it: three have their own words, the rest the generic line. */
function namedClass(riskClass: RiskClass): 'high_risk' | 'prohibited' | 'limited_risk' | 'other' {
  switch (riskClass) {
    case 'high_risk':
    case 'prohibited':
    case 'limited_risk':
      return riskClass
    case 'minimal_risk':
    case 'out_of_scope':
      return 'other'
  }
}

/** A paused result's top (artboard `ResultNeedsInfo`): where Klar paused and what the one fact
 *  decides, the stricter class it is treated as until the user answers, and what the user's
 *  lists show meanwhile. Null for a result that didn't pause on a question. */
function pausedVerdict(
  t: TFunction,
  result: ClassificationResult,
  name: string | null,
): { lead: string; treatedAs: string; lists: string } | null {
  if (result.status !== 'needs_more_information') return null
  const step = pausedStep(result)
  if (!step) return null
  const riskClass = riskClassOf(result)
  const named = namedClass(riskClass)
  const tool = name ?? t('result.pausedVerdict.theTool')
  const number = checkNumber(step.step)
  const lead =
    number === null
      ? t('result.pausedVerdict.atRole')
      : t('result.pausedVerdict.atCheck', {
          number,
          decides: t(`result.pausedVerdict.decides.${named}`, { tool }),
        })
  return {
    lead,
    treatedAs: t(`result.pausedVerdict.treatedAs.${riskClass}`),
    lists: t(`result.pausedVerdict.lists.${named}`),
  }
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
 *  date duties apply from, the Art. 111(2) notice and the legal-review line. A result paused on a
 *  question says instead where it paused and what it is treated as until the user answers. */
export function ResultVerdict({
  result,
  name = null,
  today,
}: {
  result: ClassificationResult
  /** The tool's name, for "One fact decides whether <name> is …"; null when it has none. */
  name?: string | null
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const duties = useDutiesFrom(result, today)
  const legacy = legacySentences(t, result, language)
  const paused = pausedVerdict(t, result, name)
  const summary = paused
    ? {
        statement: paused.lead,
        statusLine: paused.lists,
        dutiesFromLabel: t('result.pausedVerdict.until'),
        dutiesFrom: paused.treatedAs,
        dutiesNote: t('result.pausedVerdict.stricter'),
      }
    : {
        statement: (
          <>
            {result.role && <span>{roleLine(t, result)} </span>}
            {result.also_role && <span>{t(`result.alsoRole.${result.also_role}`)} </span>}
            <span>{basisSentence(t, result, language)}</span>
          </>
        ),
        dutiesFromLabel: t('result.dutiesFrom'),
        dutiesFrom: duties?.date,
        dutiesNote: duties?.note,
      }
  return (
    <ResultSummary
      riskClass={riskClassOf(result)}
      status={<StatusPills result={result} />}
      {...summary}
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
