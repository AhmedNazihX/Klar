import type { ClassificationResult, OpenQuestion, Reading, SettledBy, StepName } from '@/api'

/** The open question of law a legally ambiguous result rests on, with the step that left it
 *  open (E12): the first step marked legally ambiguous that carries one. */
export type OpenPoint = { step: StepName; question: OpenQuestion }

export function openPoint(result: ClassificationResult): OpenPoint | null {
  if (result.status !== 'legally_ambiguous') return null
  for (const step of result.steps) {
    if (step.status === 'legally_ambiguous' && step.open_question) {
      return { step: step.step, question: step.open_question }
    }
  }
  return null
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
