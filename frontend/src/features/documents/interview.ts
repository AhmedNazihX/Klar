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

/**
 * Blank space around an answer: the one definition the drafter uses too (`BLANK` in
 * `backend/aiact/drafting/prose.py`, whose test checks that this list is the same). It is
 * Python's whitespace (`str.isspace`) and the byte order mark; an answer of nothing else is
 * blank. `String.prototype.trim` differs: it keeps U+001C to U+001F and U+0085. They are listed
 * as code points: most would print as the invisible characters themselves.
 */
export const BLANK_CODE_POINTS = [
  0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680, 0x2000, 0x2001,
  0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a, 0x2028, 0x2029, 0x202f,
  0x205f, 0x3000, 0xfeff,
] as const
const BLANK_CHARACTERS: ReadonlySet<string> = new Set(String.fromCodePoint(...BLANK_CODE_POINTS))

/** `answer` without the blank space around it (`BLANK_CODE_POINTS`), as the drafter reads it. */
export function withoutBlank(answer: string): string {
  let start = 0
  let end = answer.length
  while (start < end && BLANK_CHARACTERS.has(answer.charAt(start))) start += 1
  while (end > start && BLANK_CHARACTERS.has(answer.charAt(end - 1))) end -= 1
  return answer.slice(start, end)
}

/** Whether a stored answer fills its question, as the drafter reads it: a blank answer, or one
 *  that names none of a choice question's choices (matched exactly, case included), leaves it to
 *  fill in. */
export function isAnswered(answers: TemplateAnswers, question: InterviewQuestion): boolean {
  const answer = withoutBlank(answers[question.key] ?? '')
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

/** The interview of a document's questions (`all`) with the answers stored for its template: it
 *  asks `chosenKey` when the user picked a question, else the first unanswered question not
 *  skipped. A skeleton's (`bySection`) covers the section of the question asked, any other all. */
export function interviewState(
  all: readonly InterviewQuestion[],
  bySection: boolean,
  answers: TemplateAnswers,
  skipped: ReadonlySet<string>,
  chosenKey: string | null,
): InterviewState {
  const open = (question: InterviewQuestion): boolean => !isAnswered(answers, question)
  const current =
    all.find((question) => question.key === chosenKey) ??
    all.find((question) => open(question) && !skipped.has(question.key)) ??
    null
  const section = bySection && current ? current.section : null
  const questions = section ? all.filter((question) => question.section === section) : all
  return {
    section,
    questions,
    answered: questions.filter((question) => !open(question)),
    current,
    upcoming: questions.filter((question) => open(question) && question.key !== current?.key),
  }
}
