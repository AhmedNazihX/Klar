import type { ClassificationResult, StepResult } from '@/api'

import { hasAssessedClass } from '@/lib/risk-class'

/** A point of the Art. 5(1) list of prohibited practices, such as `art:5:1:f`; not one of its
 *  sub-points or Art. 5(1a)'s routes (the backend reads a point the same way). */
const ART_5_POINT = /^art:5:1:[a-z]+$/

/** Art. 113(a): Art. 5 applies from 2 February 2025, the same under both texts, so the date is
 *  plain text, never a LawDate (components.md › LawDate). */
export const PROHIBITIONS_APPLY_FROM = '2025-02-02'

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

/** The Art. 5(1) points the ban rests on, each once, in the order the step cites them. */
export function banPoints(result: ClassificationResult): string[] {
  const ids = (banStep(result)?.citations ?? []).map((citation) => citation.provision_id)
  return [...new Set(ids.filter((id) => ART_5_POINT.test(id)))]
}

/** The date the tool has been banned since: the earliest start among its points, as any one of
 *  them bans it; Art. 5's own date when the step names no point. */
export function bannedSince(points: readonly string[]): string {
  const starts = points.map((point) => LATER_POINTS[point] ?? PROHIBITIONS_APPLY_FROM).sort()
  return starts[0] ?? PROHIBITIONS_APPLY_FROM
}
