import type { TFunction } from 'i18next'

import type { ClassificationResult, StepName } from '@/api'
import type { Language } from '@/i18n'

import { ORIGINAL_ROUTE_DATES, routeOfPoint, shortDate } from './dates'
import { provisionName } from './provision-names'
import { amendedRouteDate, dutiesDate, stepOutcome } from './result-text'

/** One row of "Original Act vs amended": the value under each text. */
export type ComparisonRow = {
  id: 'class' | 'basis' | 'role' | 'dutiesFrom'
  original: string
  amended: string
  /** False while the original text's value isn't known yet (it shows as not checked). */
  isKnown: boolean
}

/** A step whose outcome differs between the two texts, and the provisions the Omnibus changed in
 *  the amended step (its citations marked `changed_by_omnibus`). */
export type ChangedStep = {
  step: StepName
  original: string
  amended: string
  omnibusProvisions: string[]
}

/** The engine's checks in the Act's order, then the role and its duties. */
const COMPARED_STEPS: readonly StepName[] = [
  'scope',
  'prohibited',
  'high_risk',
  'transparency',
  'role_obligations',
]

/** The class as a pill names it, "assumed" while the result isn't decided. */
export function classLabel(t: TFunction, result: ClassificationResult): string {
  const riskClass = t(`pill.${result.risk_class}`)
  return result.status === 'decided' ? riskClass : t('diff.assumedClass', { riskClass })
}

function roleLabel(t: TFunction, result: ClassificationResult): string {
  return result.role ? t(`result.roleName.${result.role}`) : t('diff.noValue')
}

function basisLabel(result: ClassificationResult, language: Language, none: string): string {
  return result.annex_point ? provisionName(result.annex_point, language) : none
}

/** The date duties apply from under the amended text, as the result's summary shows it, or a
 *  dash when no duty is dated. */
function amendedDutiesFrom(result: ClassificationResult, language: Language, none: string): string {
  const date = dutiesDate(result)
  if (date === null) return none
  return shortDate(date.kind === 'route' ? date.amended : date.date, language)
}

/** Whether Art. 111(2) dates a high-risk result's duties: a legacy system for public authorities,
 *  whose route duties all apply from 2 August 2030, under either text. */
function isPublicAuthorityLegacy(result: ClassificationResult): boolean {
  const route = routeOfPoint(result.annex_point)
  if (result.risk_class !== 'high_risk' || route === null) return false
  const isMoved = (result.obligations ?? []).some(
    (obligation) =>
      obligation.high_risk_route === route && obligation.legacy === 'legacy_public_authority',
  )
  return isMoved && amendedRouteDate(result, route) === null
}

/** The date duties apply from under the original text, or a dash. Only the route dates move
 *  (Art. 113, decision 026 item 11): a high-risk route takes its original date, unless Art. 111(2)
 *  fixes 2030 on the same route under both texts; while the class is the same, any other date
 *  stays the amended one, as the summary shows it. A class that differs has no date Klar could
 *  name, as the original text's duties aren't modelled (decision 020). */
function originalDutiesFrom(
  amended: ClassificationResult,
  original: ClassificationResult,
  language: Language,
  none: string,
): string {
  const isSameClass = original.risk_class === amended.risk_class
  const route = original.risk_class === 'high_risk' ? routeOfPoint(original.annex_point) : null
  const isSameRoute = isSameClass && route !== null && route === routeOfPoint(amended.annex_point)
  if (route && !(isSameRoute && isPublicAuthorityLegacy(amended))) {
    return shortDate(ORIGINAL_ROUTE_DATES[route], language)
  }
  return isSameClass ? amendedDutiesFrom(amended, language, none) : none
}

/** Before the original text is checked, the one value known is a route's Art. 113 date, the
 *  summary's own swap; anything else waits for the check. */
function swappedDutiesFrom(amended: ClassificationResult, language: Language): string | null {
  const date = dutiesDate(amended)
  return date?.kind === 'route' ? shortDate(date.original, language) : null
}

/**
 * The rows of "Original Act vs amended": class, role and the date duties apply from, plus the
 * Annex point when either result has one (the route can move, e.g. machinery from Annex I B.21 to
 * A.1). Until the original text is checked, class and role show as not checked.
 */
export function comparisonRows(
  t: TFunction,
  amended: ClassificationResult,
  original: ClassificationResult | undefined,
  language: Language,
): ComparisonRow[] {
  const none = t('diff.noValue')
  const dutiesFrom = amendedDutiesFrom(amended, language, none)
  if (!original) {
    const notChecked = t('diff.notChecked')
    const swapped = swappedDutiesFrom(amended, language)
    return [
      { id: 'class', original: notChecked, amended: classLabel(t, amended), isKnown: false },
      { id: 'role', original: notChecked, amended: roleLabel(t, amended), isKnown: false },
      {
        id: 'dutiesFrom',
        original: swapped ?? notChecked,
        amended: dutiesFrom,
        isKnown: swapped !== null,
      },
    ]
  }
  const hasBasis = Boolean(amended.annex_point ?? original.annex_point)
  const rows: ComparisonRow[] = [
    {
      id: 'class',
      original: classLabel(t, original),
      amended: classLabel(t, amended),
      isKnown: true,
    },
    {
      id: 'basis',
      original: basisLabel(original, language, none),
      amended: basisLabel(amended, language, none),
      isKnown: true,
    },
    { id: 'role', original: roleLabel(t, original), amended: roleLabel(t, amended), isKnown: true },
    {
      id: 'dutiesFrom',
      original: originalDutiesFrom(amended, original, language, none),
      amended: dutiesFrom,
      isKnown: true,
    },
  ]
  return hasBasis ? rows : rows.filter((row) => row.id !== 'basis')
}

/** A step's outcome in one line, or null when the run never reached it. The role reads as the
 *  table's Role row does (a run that stopped early, at a ban, still names it); the high-risk
 *  check names its Annex point, which the Omnibus can move while the outcome stays (machinery:
 *  Annex I Section A point 1 to Section B). */
function outcomeOf(
  t: TFunction,
  result: ClassificationResult,
  step: StepName,
  language: Language,
): string | null {
  if (step === 'role_obligations') return result.role ? roleLabel(t, result) : null
  const found = result.steps.find((candidate) => candidate.step === step)
  if (!found) return null
  const outcome = stepOutcome(t, found, result)
  const point = result.risk_class === 'high_risk' ? result.annex_point : null
  if (step !== 'high_risk' || !point) return outcome
  return t('diff.steps.withPoint', { outcome, point: provisionName(point, language) })
}

function omnibusProvisions(
  result: ClassificationResult,
  step: StepName,
  language: Language,
): string[] {
  const citations = result.steps.find((candidate) => candidate.step === step)?.citations ?? []
  const ids = citations
    .filter((citation) => citation.changed_by_omnibus)
    .map((citation) => citation.provision_id)
  return [...new Set(ids)].map((id) => provisionName(id, language))
}

/** The steps both runs assessed whose outcome differs between the texts, in the Act's order,
 *  each with the provisions the Omnibus changed that the amended step rests on. A step only one
 *  run reached (the other stopped earlier, e.g. at a ban) isn't a change. */
export function changedSteps(
  t: TFunction,
  amended: ClassificationResult,
  original: ClassificationResult,
  language: Language,
): ChangedStep[] {
  return COMPARED_STEPS.flatMap((step) => {
    const before = outcomeOf(t, original, step, language)
    const after = outcomeOf(t, amended, step, language)
    if (before === null || after === null || before === after) return []
    return [
      {
        step,
        original: before,
        amended: after,
        omnibusProvisions: omnibusProvisions(amended, step, language),
      },
    ]
  })
}
