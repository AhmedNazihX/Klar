import type { ClassificationResult, StepResult } from '@/api'

import { hasAssessedClass } from '@/lib/risk-class'

import type { SummaryRowId } from './result-text'

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

/** Whether a step row reads "Not checked: a ban ends the checks": on a decided ban, the duties
 *  and every step the run never reached (the checks after Art. 5, and the role). The summary and
 *  the reviewer view read it alike; the summary then leaves the duties row out, as the artboard
 *  `ResultProhibited` stops at 4 Transparency. */
export function isUncheckedOnBan(result: ClassificationResult, id: SummaryRowId): boolean {
  if (!isDecidedBan(result) || id === 'facts') return false
  return id === 'duties' || !result.steps.some((step) => step.step === id)
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

/** A cited Art. 5(1) point that applies only after the result's date, and the day it starts. */
export type LaterPoint = { point: string; appliesFrom: string }

/** The Art. 5(1) points the step cites that don't apply yet on the result's date (the Omnibus's
 *  (ba) and (bb) before 2 December 2026), each once, in the order cited: the points `banPoints`
 *  leaves out. They decide nothing, so "Why the checks stopped" only says when each starts to
 *  apply. Built from the citations and Art. 113(a)'s dates, never from the step's decision text,
 *  whose facts may be the model's own wording. */
export function laterPoints(result: ClassificationResult): LaterPoint[] {
  const ids = (banStep(result)?.citations ?? []).map((citation) => citation.provision_id)
  const later = ids.filter((id) => ART_5_POINT.test(id) && appliesFrom(id) > result.as_of)
  return [...new Set(later)].map((point) => ({ point, appliesFrom: appliesFrom(point) }))
}

/** The date the tool has been banned since: the earliest start among the points it rests on
 *  (`banPoints`, all in force), as any one of them bans it; Art. 5's own date when the step
 *  names no point. */
export function bannedSince(points: readonly string[]): string {
  const starts = points.map(appliesFrom).sort()
  return starts[0] ?? PROHIBITIONS_APPLY_FROM
}
