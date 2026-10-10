import type {
  ClassificationResult,
  FollowUpQuestion,
  OpenQuestion,
  Reading,
  SettledBy,
  StepName,
} from '@/api'

/** The open question of law a legally ambiguous result rests on, with the step that left it
 *  open (E12): the first step marked legally ambiguous that carries one, and the provisions that
 *  step and its readings cite. */
export type OpenPoint = { step: StepName; question: OpenQuestion; provisions: string[] }

export function openPoint(result: ClassificationResult): OpenPoint | null {
  if (result.status !== 'legally_ambiguous') return null
  for (const step of result.steps) {
    const question = step.open_question
    if (step.status === 'legally_ambiguous' && question) {
      const cited = [
        ...(step.citations ?? []),
        ...question.readings.flatMap((reading) => (reading.citation ? [reading.citation] : [])),
      ]
      return {
        step: step.step,
        question,
        provisions: cited.map((citation) => citation.provision_id),
      }
    }
  }
  return null
}

/** The article or annex a provision id belongs to: `art:6:1:a` → `art:6`, `annex:III:4` →
 *  `annex:III`. */
function articleOf(provisionId: string): string {
  return provisionId.split(':').slice(0, 2).join(':')
}

/** The follow-up questions split by whether their answer bears on the open point: a question
 *  about (or quoting) an article the open step cites settles it; the others (the role, the
 *  transparency duties, Art. 111(2)) keep their own place. */
export function questionsOnPoint(
  questions: readonly FollowUpQuestion[],
  point: OpenPoint,
): { onPoint: FollowUpQuestion[]; elsewhere: FollowUpQuestion[] } {
  const articles = new Set(point.provisions.map(articleOf))
  const isOnPoint = (question: FollowUpQuestion): boolean =>
    [question.about, ...(question.citations ?? []).map((citation) => citation.provision_id)].some(
      (provisionId) => provisionId != null && articles.has(articleOf(provisionId)),
    )
  return {
    onPoint: questions.filter(isOnPoint),
    elsewhere: questions.filter((question) => !isOnPoint(question)),
  }
}

/** Where a reading's citation names a whole paragraph whose open point sits in one of its
 *  points, the point the reading rests on: the Annex I route's open question in law is whether
 *  the system is a safety component, Art. 6(1)(a) (the engine cites Art. 6(1) whole). */
const POINT_OF_READING: Readonly<Record<string, string>> = { 'art:6:1': 'art:6:1:a' }

/** The provision a reading's quote shows, at its most specific id. */
export function readingProvision(provisionId: string): string {
  return POINT_OF_READING[provisionId] ?? provisionId
}

/** One reading with its number as the cards show it. */
export type NumberedReading = { number: number; reading: Reading }

/** The readings as the cards show them (artboard `ResultAmbiguous`): the other reading first,
 *  the applied one last, numbered in that order. The engine lists the stricter, applied one
 *  first. */
export function readingsInOrder(question: OpenQuestion): NumberedReading[] {
  const applied = question.readings.filter((reading) => reading.is_applied)
  const others = question.readings.filter((reading) => !reading.is_applied)
  return [...others, ...applied].map((reading, index) => ({ number: index + 1, reading }))
}

/** What would settle the question, split by what the user can do about it: the provider's own
 *  assessment, which a request to the vendor can ask for, and guidance, which only names what it
 *  waits for (no re-check promise, decision 026 item 4). */
export function settledByKinds(question: OpenQuestion): {
  provider: SettledBy[]
  guidance: SettledBy[]
} {
  const items = question.settled_by ?? []
  return {
    provider: items.filter((item) => item.kind === 'provider'),
    guidance: items.filter((item) => item.kind === 'guidance'),
  }
}
