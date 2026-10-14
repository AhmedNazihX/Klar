import type {
  ClassificationResult,
  FollowUpQuestion,
  OpenQuestion,
  Reading,
  SettledBy,
  StepName,
} from '@/api'

/** The open question of law a legally ambiguous result rests on, with the step that left it
 *  open (E12): the first step marked legally ambiguous that carries one, and the provisions its
 *  readings cite. */
export type OpenPoint = { step: StepName; question: OpenQuestion; provisions: string[] }

/** The open point's provisions: those its readings cite, or, when they cite none, those its step
 *  cites, so a point still has something a question can bear on. */
export function openPoint(result: ClassificationResult): OpenPoint | null {
  if (result.status !== 'legally_ambiguous') return null
  for (const step of result.steps) {
    const question = step.open_question
    if (step.status === 'legally_ambiguous' && question) {
      const readingCites = question.readings.flatMap((reading) =>
        reading.citation ? [reading.citation.provision_id] : [],
      )
      const stepCites = (step.citations ?? []).map((citation) => citation.provision_id)
      return {
        step: step.step,
        question,
        provisions: readingCites.length > 0 ? readingCites : stepCites,
      }
    }
  }
  return null
}

/** Whether `provisionId` is `cited` or one of its parts: `art:6:1:a` is within `art:6:1`, while
 *  `art:6:3` and `art:6` are not. */
function isWithin(provisionId: string, cited: string): boolean {
  return provisionId === cited || provisionId.startsWith(`${cited}:`)
}

/** How deep a provision ID goes: `art:6` is an article (2), `art:6:1` a paragraph (3). */
const PARAGRAPH_DEPTH = 3

/** Whether a question about `provisionId` bears on the `cited` provision: it is the cited one, a
 *  part of it, or the paragraph (or Annex area) the cited point belongs to: a question about
 *  Art. 6(1) bears on a point open on Art. 6(1)(a). A whole article or annex is too broad. */
function bearsOn(provisionId: string, cited: string): boolean {
  if (isWithin(provisionId, cited)) return true
  return isWithin(cited, provisionId) && provisionId.split(':').length >= PARAGRAPH_DEPTH
}

/** The follow-up questions split by whether their answer bears on the open point: a question
 *  about (or quoting) a provision the point rests on, a part of one or the paragraph it belongs
 *  to, settles it; the others (another route's or provision's facts, the role, Art. 111(2)) keep
 *  their own place. */
export function questionsOnPoint(
  questions: readonly FollowUpQuestion[],
  point: OpenPoint,
): { onPoint: FollowUpQuestion[]; elsewhere: FollowUpQuestion[] } {
  const isOnPoint = (question: FollowUpQuestion): boolean =>
    [question.about, ...(question.citations ?? []).map((citation) => citation.provision_id)].some(
      (provisionId) =>
        provisionId != null && point.provisions.some((cited) => bearsOn(provisionId, cited)),
    )
  return {
    onPoint: questions.filter(isOnPoint),
    elsewhere: questions.filter((question) => !isOnPoint(question)),
  }
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
