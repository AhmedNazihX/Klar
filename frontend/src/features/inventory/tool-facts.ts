import type { ClassificationResult, Obligation, RiskClass } from '@/api'
import { dutiesDate, isTransparencyDuty } from '@/features/classify/result-text'
import { isLawProvision, provisionName } from '@/features/classify/provision-names'
import type { Language } from '@/i18n'
import type { InventoryTool } from '@/lib/inventory'

// What the inventory shows about one tool, read from its latest result (artboard `Inventory`).

/** A tool with a readable result. */
export type CheckedTool = InventoryTool & { result: ClassificationResult }

export function isChecked(tool: InventoryTool): tool is CheckedTool {
  return tool.result !== null
}

/** The classes from the strictest down: the table's order and the summary's. */
export const CLASS_ORDER: readonly RiskClass[] = [
  'prohibited',
  'high_risk',
  'limited_risk',
  'minimal_risk',
  'out_of_scope',
]

/** Strictest class first; tools without a readable result last. Otherwise the order they came in
 *  (oldest first). */
export function sortTools(tools: readonly InventoryTool[]): InventoryTool[] {
  const rank = (tool: InventoryTool): number =>
    tool.result ? CLASS_ORDER.indexOf(tool.result.risk_class) : CLASS_ORDER.length
  return tools
    .map((tool, index) => ({ tool, index }))
    .sort((a, b) => rank(a.tool) - rank(b.tool) || a.index - b.index)
    .map(({ tool }) => tool)
}

/** Today as an ISO date (YYYY-MM-DD) in the viewer's calendar, to compare with `applies_from`. */
export function isoDay(today: Date): string {
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${String(today.getFullYear())}-${month}-${day}`
}

/** The "Applies from" column. */
export type AppliesFrom =
  /** No duty to date (minimal risk, out of scope). */
  | { kind: 'none' }
  /** The route's Chapter III date, which the Digital Omnibus moved (a LawDate). */
  | { kind: 'route'; amended: string; original: string }
  /** A date still ahead. */
  | { kind: 'from'; date: string }
  /** A date that has come. */
  | { kind: 'since'; date: string }
  /** Art. 111(2): the high-risk duties apply only after a significant change. */
  | { kind: 'afterChange' }
  /** Art. 111(2): a system for public authorities, its high-risk duties from 2 August 2030. */
  | { kind: 'legacyFrom'; date: string }

function routeDuties(result: ClassificationResult): Obligation[] {
  return (result.obligations ?? []).filter((obligation) => obligation.high_risk_route)
}

/** The Art. 111(2) marking when it covers every one of the route's duties (decision 022). */
function legacyAppliesFrom(result: ClassificationResult): AppliesFrom | null {
  const duties = routeDuties(result)
  if (duties.length === 0 || !duties.every((duty) => duty.legacy)) return null
  const forAuthorities = duties.find((duty) => duty.legacy === 'legacy_public_authority')
  return forAuthorities
    ? { kind: 'legacyFrom', date: forAuthorities.applies_from }
    : { kind: 'afterChange' }
}

function dated(isoDate: string, today: Date): AppliesFrom {
  return isoDate <= isoDay(today)
    ? { kind: 'since', date: isoDate }
    : { kind: 'from', date: isoDate }
}

/** A limited-risk tool's date is its Art. 50 duties' (the general Art. 4 duty doesn't date it). */
function transparencyAppliesFrom(result: ClassificationResult, today: Date): AppliesFrom {
  const [earliest] = (result.obligations ?? [])
    .filter((duty) => isTransparencyDuty(duty) && !duty.is_informational)
    .map((duty) => duty.applies_from)
    .sort()
  return earliest ? dated(earliest, today) : { kind: 'none' }
}

/** When the tool's duties apply, as the result dated them; `today` decides "since" or "from". */
export function appliesFrom(result: ClassificationResult, today: Date): AppliesFrom {
  switch (result.risk_class) {
    case 'minimal_risk':
    case 'out_of_scope':
      return { kind: 'none' }
    case 'limited_risk':
      return transparencyAppliesFrom(result, today)
    case 'high_risk':
    case 'prohibited': {
      const legacy = result.risk_class === 'high_risk' ? legacyAppliesFrom(result) : null
      if (legacy) return legacy
      const date = dutiesDate(result)
      if (date === null) return { kind: 'none' }
      if (date.kind === 'route') {
        return { kind: 'route', amended: date.amended, original: date.original }
      }
      return dated(date.date, today)
    }
  }
}

function firstLawReference(result: ClassificationResult, step: string): string | null {
  const citations = result.steps.find((candidate) => candidate.step === step)?.citations ?? []
  return citations.map((citation) => citation.provision_id).find(isLawProvision) ?? null
}

/** The provision whose two readings left the result legally ambiguous, if the step names one. */
export function ambiguousProvision(result: ClassificationResult): string | null {
  const step = result.steps.find((candidate) => candidate.status === 'legally_ambiguous')
  if (!step) return null
  const [stricter] = step.open_question?.readings ?? []
  const quoted = stricter?.citation?.provision_id
  if (quoted && isLawProvision(quoted)) return quoted
  return (
    (step.citations ?? []).map((citation) => citation.provision_id).find(isLawProvision) ?? null
  )
}

/** The provision ids the class rests on, for the "Basis" column; empty when there is none to
 *  name (minimal risk names no duty instead). */
function basisIds(result: ClassificationResult): string[] {
  switch (result.risk_class) {
    case 'high_risk': {
      const ids = [result.annex_point, ambiguousProvision(result)]
      return [...new Set(ids.filter((id): id is string => Boolean(id)))]
    }
    case 'prohibited': {
      const id = firstLawReference(result, 'prohibited')
      return id ? [id] : []
    }
    case 'limited_risk': {
      const duties = result.transparency_duties ?? []
      if (duties.length === 0) return []
      const [only] = duties
      return duties.length === 1 && only ? [only] : ['art:50']
    }
    case 'out_of_scope': {
      const id = firstLawReference(result, 'scope')
      return id ? [id] : []
    }
    case 'minimal_risk':
      return []
  }
}

/** The "Basis" column's provisions in the screen's language, e.g. ["Annex III 4(a)", "Art. 6(3)"]. */
export function basisReferences(result: ClassificationResult, language: Language): string[] {
  return basisIds(result).map((id) => provisionName(id, language))
}

/** How many questions a paused result waits for: one per check that paused on a missing fact. */
export function openQuestionCount(result: ClassificationResult): number {
  const paused = result.steps.filter(
    (step) => step.status === 'needs_more_information' && step.missing_fact,
  )
  return Math.max(1, paused.length)
}

/**
 * The table's one-line "what" (the cell cuts it with an ellipsis where it runs out of room). A
 * description often opens with the company ("We're a 40-person logistics company."), so it is
 * the first fact the prohibited-practices check used, which states what the tool does in the
 * result's words; an assumed fact is left out (it says what the description doesn't). Without
 * one, the description's first line, whole: the cell's ellipsis shortens it, so no full stop
 * (in "e.g." or "z. B.") is taken for a sentence's end.
 */
export function whatItDoes(tool: InventoryTool): string {
  const practices = tool.result?.steps.find((step) => step.step === 'prohibited')
  const fact = practices?.facts_used?.find((used) => used.evidence !== 'assumed')
  if (fact) return fact.text
  const [line = ''] = tool.description.trim().split(/\r?\n/, 1)
  return line
}
