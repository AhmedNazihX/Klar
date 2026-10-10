import type { ClassificationResult, LawVersion, Obligation, ObligationGroup } from '@/api'
import type { SizeClass } from '@/lib/company-profile'

// The provider layout (artboard `ResultProvider`, P23): which results get it, how its duties are
// grouped, and which of its notes apply. Pure, so each rule is tested on its own.

/** The three groups in the layout's order, as C9's obligations table sets them. */
export const DUTY_GROUPS: readonly ObligationGroup[] = ['build', 'prove', 'after_launch']

/** The Art. 11(1) duty, whose draft opens as a skeleton (artboard `DocSkeleton`). */
export const TECHNICAL_DOCUMENTATION_ARTICLE = 'art:11:1'

/** The definition the role step cites when a system built on a general-purpose AI model made
 *  the company its provider (Art. 3(68), the engine's `DOWNSTREAM_PROVIDER_ARTICLE`). */
const DOWNSTREAM_PROVIDER = 'art:3:68'
/** The role step's question whether the system is built on a general-purpose AI model. */
const BUILDS_ON_GPAI = 'builds_on_gpai'

/** Annex III points 2 to 8: conformity by internal control, no notified body (Art. 43(2)). */
const INTERNAL_CONTROL_POINTS: ReadonlySet<string> = new Set(['2', '3', '4', '5', '6', '7', '8'])

/** A high-risk result for a provider gets the provider layout (a decided ban keeps its own). A
 *  legally ambiguous one doesn't: it has the ambiguous layout (artboard `ResultAmbiguous`, P22). */
export function isProviderLayout(result: ClassificationResult): boolean {
  return (
    result.role === 'provider' &&
    result.risk_class === 'high_risk' &&
    result.status !== 'legally_ambiguous'
  )
}

/** The role step, if it ran. */
function roleStep(result: ClassificationResult): ClassificationResult['steps'][number] | null {
  return result.steps.find((step) => step.step === 'role_obligations') ?? null
}

/** Whether the GPAI question is still open: then the system may not be built on one. */
function isGpaiAsked(result: ClassificationResult): boolean {
  const asked = [
    ...(result.follow_up_questions ?? []),
    ...result.steps.flatMap((step) => (step.missing_fact ? [step.missing_fact] : [])),
  ]
  return asked.some((question) => question.id === BUILDS_ON_GPAI)
}

/**
 * The company provides a system built on another company's general-purpose AI model: the role
 * step cites the downstream-provider definition (Art. 3(68)), which it does for a yes, and the
 * question isn't open (an unknown answer is asked, and also cites it as the fact it waits on).
 */
export function isGpaiBased(result: ClassificationResult): boolean {
  if (result.role !== 'provider') return false
  const cited = roleStep(result)?.citations ?? []
  const citesDefinition = cited.some((citation) => citation.provision_id === DOWNSTREAM_PROVIDER)
  return citesDefinition && !isGpaiAsked(result)
}

/** The Art. 25(1) points a switch can rest on; the engine cites every one that applies. */
const SWITCH_POINTS = ['a', 'b', 'c'] as const

/** Every set of Art. 25(1) points, by its letters in order, with its role sentence. */
const SWITCH_REASONS = {
  a: 'switch_a',
  b: 'switch_b',
  c: 'switch_c',
  ab: 'switch_ab',
  ac: 'switch_ac',
  bc: 'switch_bc',
  abc: 'switch_abc',
} as const

/** Why the company is the provider, for the role sentence: every Art. 25(1) point the role step
 *  cites for a switch, the GPAI build route, or in its own right (Art. 3(3)); `stated` when the
 *  role step didn't settle it (an assumed or ambiguous role) or cites no Art. 25(1) point for a
 *  switch, so the sentence claims no reason. */
export type ProviderReason =
  (typeof SWITCH_REASONS)[keyof typeof SWITCH_REASONS] | 'gpai' | 'own' | 'stated'

function isSwitchSet(letters: string): letters is keyof typeof SWITCH_REASONS {
  return letters in SWITCH_REASONS
}

export function providerReason(result: ClassificationResult): ProviderReason {
  const step = roleStep(result)
  if (step?.status !== undefined && step.status !== 'decided') return 'stated'
  if (!result.role_switch_reason) return isGpaiBased(result) ? 'gpai' : 'own'
  const cited = new Set((step?.citations ?? []).map((citation) => citation.provision_id))
  const letters = SWITCH_POINTS.filter((point) => cited.has(`art:25:1:${point}`)).join('')
  return isSwitchSet(letters) ? SWITCH_REASONS[letters] : 'stated'
}

export type DutyGroups = Record<ObligationGroup, Obligation[]> & {
  /** Duties without a group: those of the role the company keeps (a deployer's, Art. 26). On a
   *  result saved before C9 grouped the duties, the provider's own land here too. */
  other: Obligation[]
}

/** The result's duties by group, each in the engine's order. */
export function groupDuties(obligations: readonly Obligation[]): DutyGroups {
  const of = (group: ObligationGroup | null): Obligation[] =>
    obligations.filter((duty) => (duty.group ?? null) === group)
  return {
    build: of('build'),
    prove: of('prove'),
    after_launch: of('after_launch'),
    other: of(null),
  }
}

/** The Annex III point number (`annex:III:4:b` → "4") when Art. 43(2) applies to it. */
export function internalControlPoint(result: ClassificationResult): string | null {
  const [kind, annex, point] = (result.annex_point ?? '').split(':')
  if (kind !== 'annex' || annex !== 'III' || point === undefined) return null
  return INTERNAL_CONTROL_POINTS.has(point) ? point : null
}

/**
 * Who may use Art. 11(1)'s simplified documentation form, from the company profile's size class:
 * an SME under either text, a small mid-cap only under the amended text (the Omnibus added them,
 * so neither the original text nor a result run under it names them). Null for "neither" or no
 * profile.
 */
export function simplifiedFormFor(
  sizeClass: SizeClass | null | undefined,
  shown: LawVersion,
  result: ClassificationResult,
): 'sme' | 'smc' | null {
  if (sizeClass === 'sme') return 'sme'
  const isAmended = shown === 'amended' && result.law_version === 'amended'
  return sizeClass === 'smc' && isAmended ? 'smc' : null
}
