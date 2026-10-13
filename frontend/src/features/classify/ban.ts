import type { ClassificationResult, StepResult } from '@/api'

import { hasAssessedClass } from '@/lib/risk-class'

import { restingFacts } from './result-text'

/** A point of the Art. 5(1) list of prohibited practices, such as `art:5:1:f`; not one of its
 *  sub-points or Art. 5(1a)'s routes (the backend reads a point the same way). */
const ART_5_POINT = /^art:5:1:[a-z]+$/

/** Art. 113(a): Art. 5 applies from 2 February 2025, the same under both texts, so the date is
 *  plain text, never a LawDate (components.md › LawDate). */
const PROHIBITIONS_APPLY_FROM = '2025-02-02'

/** The points the Omnibus added, which apply only from 2 December 2026 (Art. 113(a) as amended).
 *  The original text has no such points, so their date doesn't move between the texts either. */
const LATER_POINTS: Readonly<Record<string, string>> = {
  'art:5:1:ba': '2026-12-02',
  'art:5:1:bb': '2026-12-02',
}

/** Whether the result gets the prohibited layout: a decided ban whose every check was assessed.
 *  A refused check carries no class (decision 030), so it never reaches this layout; an assumed
 *  ban keeps the summary that asks its question. */
export function isDecidedBan(result: ClassificationResult): boolean {
  return (
    hasAssessedClass(result) && result.risk_class === 'prohibited' && result.status === 'decided'
  )
}

/** The Art. 5 step, which stopped the checks. */
export function banStep(result: ClassificationResult): StepResult | undefined {
  return result.steps.find((step) => step.step === 'prohibited')
}

/** The day an Art. 5(1) point starts to apply (Art. 113(a)). */
function appliesFrom(point: string): string {
  return LATER_POINTS[point] ?? PROHIBITIONS_APPLY_FROM
}

/** The Art. 5(1) points the ban rests on: those the step cites that apply on the result's date,
 *  each once, in the order cited. The engine also cites a point that applies only later (the
 *  Omnibus's (ba) and (bb) before 2 December 2026); it doesn't decide the ban, and the corpus has
 *  no text of it at that date. The vendor letter reads the points the same way (backend
 *  `vendor_letters.fills.deciding_points`), so the verdict, "Why the checks stopped" and the
 *  letter name the same points. ISO dates compare as strings. */
export function banPoints(result: ClassificationResult): string[] {
  const ids = (banStep(result)?.citations ?? []).map((citation) => citation.provision_id)
  const points = ids.filter((id) => ART_5_POINT.test(id) && appliesFrom(id) <= result.as_of)
  return [...new Set(points)]
}

/** The opening sentence of a decided ban's Art. 5 decision, "Prohibited under Art. 5(1)(f)." in
 *  the run's language (backend `prohibited_texts.TEXTS`). It ends at the first full stop before a
 *  capital or the end, so the stops inside "Art. 5 Abs. 1 Buchst. f" don't end it. */
const BAN_LEAD = /^(?:Prohibited under|Verboten nach) .+?\.(?=\s+\p{Lu}|\s*$)/u

/** `text` without the first of `prefixes` it starts with, trimmed; null when none does. */
function withoutPrefix(text: string, prefixes: readonly string[]): string | null {
  const prefix = prefixes.find((candidate) => candidate !== '' && text.startsWith(candidate))
  return prefix === undefined ? null : text.slice(prefix.length).trim()
}

/** What the Art. 5 step's decision adds to the screen around "Why the checks stopped", or null.
 *  A decided ban's decision is its opening sentence, then each deciding fact, then a sentence for
 *  each point that applies only later (backend `prohibited._finding`). The verdict and the
 *  heading already name the points, and the facts panel beside it shows the facts, so only the
 *  rest is new. */
export function banDecisionNote(result: ClassificationResult): string | null {
  const step = banStep(result)
  if (!step) return null
  const facts = [...restingFacts(result), ...(step.facts_used ?? [])].map((fact) => fact.text)
  let rest = step.decision.trim().replace(BAN_LEAD, '').trim()
  for (let next = withoutPrefix(rest, facts); next !== null; next = withoutPrefix(rest, facts)) {
    rest = next
  }
  return rest === '' ? null : rest
}

/** The date the tool has been banned since: the earliest start among the points it rests on
 *  (`banPoints`, all in force), as any one of them bans it; Art. 5's own date when the step
 *  names no point. */
export function bannedSince(points: readonly string[]): string {
  const starts = points.map(appliesFrom).sort()
  return starts[0] ?? PROHIBITIONS_APPLY_FROM
}
