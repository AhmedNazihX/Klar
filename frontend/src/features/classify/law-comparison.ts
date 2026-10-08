import type { TFunction } from 'i18next'

import type { ClassificationResult, StepName } from '@/api'
import type { Language } from '@/i18n'

import { ORIGINAL_ROUTE_DATES, routeOfPoint, shortDate } from './dates'
import { provisionName } from './provision-names'
import { dutiesDate, stepOutcome } from './result-text'

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

/** The classes with no duties to date, under either text. */
const UNDATED_CLASSES: ReadonlySet<ClassificationResult['risk_class']> = new Set([
  'minimal_risk',
  'out_of_scope',
])

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

/** The date duties apply from under the amended text, as the result's summary shows it. */
function amendedDutiesFrom(t: TFunction, result: ClassificationResult, language: Language): string {
  const date = dutiesDate(result)
  if (date === null) return t('result.steps.noDuties')
  return shortDate(date.kind === 'route' ? date.amended : date.date, language)
}

/** The date duties apply from under the original text. Only the route dates move (Art. 113,
 *  decision 026 item 11): a high-risk route takes its original date; while the class is the
 *  same, any other date (or none) stays the amended one, as the summary shows it; a class that
 *  differs has dated duties only if it is minimal risk or out of scope (none), otherwise none Klar
 *  could name, as the original text's duties aren't modelled (decision 020). */
function originalDutiesFrom(
  t: TFunction,
  amended: ClassificationResult,
  original: ClassificationResult,
  language: Language,
): string {
  const route = original.risk_class === 'high_risk' ? routeOfPoint(original.annex_point) : null
  if (route) return shortDate(ORIGINAL_ROUTE_DATES[route], language)
  if (original.risk_class === amended.risk_class) {
    const date = dutiesDate(amended)
    if (date === null) return t('result.steps.noDuties')
    if (date.kind === 'fixed') return shortDate(date.date, language)
    return t('diff.notModelled')
  }
  if (UNDATED_CLASSES.has(original.risk_class)) return t('result.steps.noDuties')
  return t('diff.notModelled')
}

/** Before the original text is checked, only the date is known: the summary's own swap. */
function swappedDutiesFrom(
  t: TFunction,
  amended: ClassificationResult,
  language: Language,
): string {
  const date = dutiesDate(amended)
  if (date === null) return t('result.steps.noDuties')
  return shortDate(date.kind === 'route' ? date.original : date.date, language)
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
  const dutiesFrom = amendedDutiesFrom(t, amended, language)
  if (!original) {
    const notChecked = t('diff.notChecked')
    return [
      { id: 'class', original: notChecked, amended: classLabel(t, amended), isKnown: false },
      { id: 'role', original: notChecked, amended: roleLabel(t, amended), isKnown: false },
      {
        id: 'dutiesFrom',
        original: swappedDutiesFrom(t, amended, language),
        amended: dutiesFrom,
        isKnown: true,
      },
    ]
  }
  const none = t('diff.noValue')
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
      original: originalDutiesFrom(t, amended, original, language),
      amended: dutiesFrom,
      isKnown: true,
    },
  ]
  return hasBasis ? rows : rows.filter((row) => row.id !== 'basis')
}

/** A step's outcome in one line; the high-risk check names its Annex point, which the Omnibus
 *  can move while the outcome stays (machinery: Annex I Section A point 1 to Section B). */
function outcomeOf(
  t: TFunction,
  result: ClassificationResult,
  step: StepName,
  language: Language,
): string {
  const found = result.steps.find((candidate) => candidate.step === step)
  if (!found) return t('result.steps.notChecked')
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

/** The steps whose outcome differs between the texts, in the Act's order, each with the
 *  provisions the Omnibus changed that the amended step rests on. */
export function changedSteps(
  t: TFunction,
  amended: ClassificationResult,
  original: ClassificationResult,
  language: Language,
): ChangedStep[] {
  return COMPARED_STEPS.flatMap((step) => {
    const before = outcomeOf(t, original, step, language)
    const after = outcomeOf(t, amended, step, language)
    if (before === after) return []
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
