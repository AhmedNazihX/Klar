import i18n, { type TFunction } from 'i18next'

import type {
  Citation,
  ClassificationResult,
  Fact,
  FollowUpQuestion,
  HighRiskRoute,
  Obligation,
  Status,
  StepName,
  StepResult,
} from '@/api'
import type { Status as PillStatus } from '@/components/pill-kinds'
import type { Language } from '@/i18n'
import type en from '@/i18n/locales/en.json'

import { longDate, routeDates, routeOfPoint } from './dates'
import { annexPointKey, isLawProvision, provisionName } from './provision-names'
import { riskClassOf } from '@/lib/risk-class'

/** The summary and reviewer's step rows, in the Act's order: Facts, Role, the four checks, Duties. */
export const SUMMARY_ROWS = [
  'facts',
  'role_obligations',
  'scope',
  'prohibited',
  'high_risk',
  'transparency',
  'duties',
] as const
export type SummaryRowId = (typeof SUMMARY_ROWS)[number]

/** The StatusPill look of an engine status: the uncertain ones never look decided. */
export function statusPill(status: Status): Exclude<PillStatus, 'draft'> {
  switch (status) {
    case 'decided':
      return 'decided'
    case 'legally_ambiguous':
      return 'ambiguous'
    case 'needs_more_information':
      return 'needs-info'
  }
}

/** Each fact once: a fact's text is its identity (the engine lists a fact once per step). */
export function uniqueFacts(facts: readonly Fact[]): Fact[] {
  return [...new Map(facts.map((fact) => [fact.text, fact])).values()]
}

/** The facts a result rests on, each once: the deciding facts, or every fact of a result that
 *  names none. The facts panel shows these and the Facts step row counts them, so the two agree. */
export function restingFacts(result: ClassificationResult): Fact[] {
  const deciding = result.deciding_facts ?? []
  return uniqueFacts(deciding.length > 0 ? deciding : result.facts)
}

/** How many provisions a collapsed step row names; the rest are in its expanded card. */
const MAX_ROW_REFERENCES = 3

type AnnexPointKey = keyof typeof en.annexPoint

function isAnnexPointKey(key: string): key is AnnexPointKey {
  return i18n.exists(`annexPoint.${key}`)
}

/** An Annex III point's plain label ("recruitment and selection of people"), if the app has one. */
export function annexLabel(t: TFunction, pointId: string): string | null {
  const key = annexPointKey(pointId)
  return key !== null && isAnnexPointKey(key) ? t(`annexPoint.${key}`) : null
}

/** The sentence on why the class applies: the Annex point for High-risk, the class otherwise. */
export function basisSentence(
  t: TFunction,
  result: ClassificationResult,
  language: Language,
): string {
  const point = result.annex_point
  if (result.risk_class === 'high_risk' && point) {
    const name = provisionName(point, language)
    if (routeOfPoint(point) === 'annex_i') return t('result.basis.annexI', { point: name })
    const label = annexLabel(t, point)
    return label
      ? t('result.basis.annexIII', { point: name, label })
      : t('result.basis.annexIIIPlain', { point: name })
  }
  return t(`result.basis.${riskClassOf(result)}`)
}

/** An Art. 50 transparency duty (`art:50` or one of its paragraphs). */
export function isTransparencyDuty(obligation: Obligation): boolean {
  return obligation.article === 'art:50' || obligation.article.startsWith('art:50:')
}

/** The duty in plain words: C9's short action label in the screen's language, or the provision's
 *  name for a stored result from before C9, which has no labels. */
export function dutyLabel(obligation: Obligation, language: Language): string {
  const label = language === 'de' ? obligation.label_de : obligation.label_en
  return label || provisionName(obligation.article, language)
}

/** A duty list's article column is wider in German (localisation.md: "Art. 26 Abs. 11"). */
export const DUTY_REFERENCE_WIDTH: Record<Language, number> = { en: 86, de: 112 }

/** A duty's condition in the screen's language. A duty stored before its German condition
 *  existed (P11), or whose condition the table no longer holds, keeps its English one. */
export function dutyCondition(obligation: Obligation, language: Language): string | null {
  const german = language === 'de' ? obligation.applies_if_de : null
  return german || obligation.applies_if || null
}

/** The line under a duty: its Art. 111(2) marking (decision 026 item 24), or its condition. */
export function dutyNote(t: TFunction, obligation: Obligation, language: Language): string | null {
  if (obligation.legacy === 'legacy_unchanged') return t('result.legacy.afterChange')
  if (obligation.legacy === 'legacy_public_authority') {
    return t('result.legacy.from', { date: longDate(obligation.applies_from, language) })
  }
  if (obligation.applies_if) {
    return t('result.todo.onlyIf', { condition: dutyCondition(obligation, language) })
  }
  if (obligation.is_informational) return t('result.todo.forInformation')
  return null
}

/** A tool's name, or "Your tool" in the screen's language when the user gave none. */
export function toolName(t: TFunction, name: string | null): string {
  return name ?? t('classify.untitled')
}

/** The date duties apply from: the route's dates (moved by the Omnibus) on a High-risk result,
 *  otherwise the earliest date of a duty to do. */
type DutiesDate =
  { kind: 'route'; amended: string; original: string } | { kind: 'fixed'; date: string }

/** The route's Chapter III date as the engine dated the route's duties (amended text); a duty
 *  Art. 111(2) moves to 2030 doesn't count. */
export function amendedRouteDate(
  result: ClassificationResult,
  route: HighRiskRoute,
): string | null {
  const duty = (result.obligations ?? []).find(
    (obligation) =>
      obligation.high_risk_route === route && obligation.legacy !== 'legacy_public_authority',
  )
  return duty?.applies_from ?? null
}

/** The date Art. 111(2) moved a high-risk result's route duties to (2 August 2030, a system for
 *  public authorities), the same under either text; null when no route duty was moved. */
export function publicAuthorityLegacyDate(result: ClassificationResult): string | null {
  const route = routeOfPoint(result.annex_point)
  if (route === null || result.risk_class !== 'high_risk') return null
  if (amendedRouteDate(result, route) !== null) return null
  const moved = (result.obligations ?? []).find(
    (obligation) =>
      obligation.high_risk_route === route && obligation.legacy === 'legacy_public_authority',
  )
  return moved?.applies_from ?? null
}

export function dutiesDate(result: ClassificationResult): DutiesDate | null {
  const route = routeOfPoint(result.annex_point)
  if (route && result.risk_class === 'high_risk') {
    const amended = amendedRouteDate(result, route)
    if (amended) return { kind: 'route', ...routeDates(route, amended) }
    const moved = publicAuthorityLegacyDate(result)
    if (moved !== null) return { kind: 'fixed', date: moved }
  }
  const dates = (result.obligations ?? [])
    .filter((obligation) => !obligation.is_informational)
    .map((obligation) => obligation.applies_from)
    .sort()
  const [earliest] = dates
  return earliest === undefined ? null : { kind: 'fixed', date: earliest }
}

/** The first step that paused for a missing fact, with its question. */
export function pausedStep(
  result: ClassificationResult,
): (StepResult & { missing_fact: FollowUpQuestion }) | null {
  for (const step of result.steps) {
    if (step.status === 'needs_more_information' && step.missing_fact) {
      return { ...step, missing_fact: step.missing_fact }
    }
  }
  return null
}

/** The step that decided the class, for the reviewer's highlighted card. */
export function decidingStep(result: ClassificationResult): StepName | null {
  switch (riskClassOf(result)) {
    case 'out_of_scope':
      return 'scope'
    case 'prohibited':
      return 'prohibited'
    case 'high_risk':
      return 'high_risk'
    case 'limited_risk':
      return 'transparency'
    case 'minimal_risk':
      return null
  }
}

/** The provisions a collapsed step row names: the Act's own first, a few at most. */
export function rowReferences(citations: readonly Citation[], language: Language): string[] {
  const ids = [...new Set(citations.map((citation) => citation.provision_id))]
  const law = ids.filter(isLawProvision)
  return (law.length > 0 ? law : ids)
    .slice(0, MAX_ROW_REFERENCES)
    .map((id) => provisionName(id, language))
}

/** "Art. 6(3), English": where a quote comes from, with "draft" on draft guidance. */
export function citationSource(t: TFunction, citation: Citation, language: Language): string {
  const values = {
    provision: provisionName(citation.provision_id, language),
    language: t(`result.quoteLanguage.${citation.language}`),
  }
  return citation.document_status === 'draft'
    ? t('result.citationSourceDraft', values)
    : t('result.citationSource', values)
}

function highRiskOutcome(t: TFunction, result: ClassificationResult): string {
  if (result.risk_class !== 'high_risk') return t('result.steps.notHighRisk')
  const point = result.annex_point
  if (routeOfPoint(point) === 'annex_i') return t('result.steps.highRiskAnnexI')
  const label = point ? annexLabel(t, point) : null
  return label ? t('result.steps.highRiskAnnexIII', { label }) : t('result.steps.highRisk')
}

/** A step's outcome in one plain line, for its collapsed row. */
export function stepOutcome(t: TFunction, step: StepResult, result: ClassificationResult): string {
  if (step.status === 'needs_more_information') return t('result.steps.paused')
  if (step.status === 'legally_ambiguous') return t('result.steps.ambiguous')
  switch (step.step) {
    case 'scope':
      return result.risk_class === 'out_of_scope'
        ? t('result.steps.outOfScope')
        : t('result.steps.inScope')
    case 'prohibited':
      return result.risk_class === 'prohibited' ? t('result.steps.ban') : t('result.steps.noBan')
    case 'high_risk':
      return highRiskOutcome(t, result)
    case 'transparency': {
      const count = result.transparency_duties?.length ?? 0
      return count > 0
        ? t('result.steps.transparencyDuties', { count })
        : t('result.steps.noTransparency')
    }
    case 'role_obligations':
      return result.role ? t(`result.roleName.${result.role}`) : t('result.steps.notChecked')
  }
}
