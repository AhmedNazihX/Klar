import type { CheckedDraft, InterviewQuestion } from '@/api'

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

/** Whether a stored answer fills its question: the drafter leaves a blank one out. */
export function isAnswered(answers: Readonly<Record<string, string>>, key: string): boolean {
  return (answers[key] ?? '').trim() !== ''
}

/** The interview of `draft` with the answers stored for its template: it asks `chosenKey` when
 *  the user picked a question, else the first unanswered question not skipped. */
export function interviewState(
  draft: CheckedDraft,
  answers: Readonly<Record<string, string>>,
  skipped: ReadonlySet<string>,
  chosenKey: string | null,
): InterviewState {
  const all = draft.questions
  const open = (question: InterviewQuestion): boolean => !isAnswered(answers, question.key)
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
