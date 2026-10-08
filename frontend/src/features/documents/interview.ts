import type { CheckedDraft, InterviewQuestion } from '@/api'

/** One document's stored answers, by question key. */
export type TemplateAnswers = Readonly<Record<string, string>>

/** Where the guided interview stands for one document. A skeleton's interview runs section by
 *  section (decision 026 item 21): its scope is the section of the question asked. */
export type InterviewState = {
  /** The key of the section the interview is in, for a skeleton; null for a short document. */
  section: string | null
  /** The questions in scope, in the order asked. */
  questions: readonly InterviewQuestion[]
  answered: readonly InterviewQuestion[]
  /** The question asked now; null when every question in scope is answered or skipped. */
  current: InterviewQuestion | null
  upcoming: readonly InterviewQuestion[]
}

/** Whether the document is a skeleton: its sections quote the requirement they answer. */
export function isSkeleton(draft: CheckedDraft): boolean {
  return draft.document.sections.some((section) => section.requirement != null)
}

/** Whether a stored answer fills its question, as the drafter reads it: a blank answer, or one
 *  that names none of a choice question's choices, leaves it to fill in. */
export function isAnswered(answers: TemplateAnswers, question: InterviewQuestion): boolean {
  const answer = (answers[question.key] ?? '').trim()
  const choices = question.choices ?? []
  if (choices.length > 0) return choices.some((choice) => choice.key === answer)
  return answer !== ''
}

/** How many of `questions` the answers leave to fill in: a document's "Needs N answers". */
export function unansweredCount(
  questions: readonly InterviewQuestion[],
  answers: TemplateAnswers,
): number {
  return questions.filter((question) => !isAnswered(answers, question)).length
}

/** The interview of `draft` with the answers stored for its template: it asks `chosenKey` when
 *  the user picked a question, else the first unanswered question not skipped. */
export function interviewState(
  draft: CheckedDraft,
  answers: TemplateAnswers,
  skipped: ReadonlySet<string>,
  chosenKey: string | null,
): InterviewState {
  const all = draft.questions
  const open = (question: InterviewQuestion): boolean => !isAnswered(answers, question)
  const current =
    all.find((question) => question.key === chosenKey) ??
    all.find((question) => open(question) && !skipped.has(question.key)) ??
    null
  const section = isSkeleton(draft) && current ? current.section : null
  const questions = section ? all.filter((question) => question.section === section) : all
  return {
    section,
    questions,
    answered: questions.filter((question) => !open(question)),
    current,
    upcoming: questions.filter((question) => open(question) && question.key !== current?.key),
  }
}
