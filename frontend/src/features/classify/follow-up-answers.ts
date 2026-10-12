import type { TFunction } from 'i18next'

import type { AnswerOption, ClassificationResult, FollowUpQuestion } from '@/api'
import { EU_MEMBER_STATES } from '@/features/welcome/countries'
import type { CompanyProfile } from '@/lib/company-profile'
import type { Answers } from '@/lib/tool-runs'

import { pausedStep, restingFacts } from './result-text'

// The follow-up loop's answers (story P5b, decision 019): what the user picked or wrote for each
// key-fact question becomes one line of text the engine reads appended to the description. The
// API bounds them (ClassifyRequest: ids are slugs, at most 40 answers of 1000 characters, none
// blank), so nothing here can send a request it refuses.

/** A question's id, as the API takes it (`SLUG_PATTERN` in aiact/schemas/questions.py). */
const ANSWER_ID = /^[a-z][a-z0-9_]{0,63}$/
/** ClassifyRequest.MAX_ANSWER_CHARS. */
export const MAX_ANSWER_CHARS = 1000
/** ClassifyRequest.MAX_ANSWERS. */
export const MAX_ANSWERS = 40

/** Yes, No and Not sure, in the order the screens offer them. */
export const ANSWER_OPTIONS: readonly AnswerOption[] = ['yes', 'no', 'not_sure']

/** What the user has given for one question so far: a choice, or words. */
export type AnswerDraft = { option?: AnswerOption; text?: string }
export type AnswerDrafts = Readonly<Record<string, AnswerDraft>>

/** The Art. 2(1) question the company profile can answer (decision 026 item 2). */
const EU_LINK = 'eu_link'

/** The options a question offers: Yes, No and Not sure for a yes/no question; none for a question
 *  answered in words. A stored result was written by the browser, so unknown values are dropped. */
export function optionsOf(question: FollowUpQuestion): AnswerOption[] {
  return ANSWER_OPTIONS.filter((option) => question.options?.includes(option))
}

/** A question the loop can send an answer to. */
export function isAnswerable(question: FollowUpQuestion): boolean {
  return ANSWER_ID.test(question.id)
}

/** The result's follow-up questions the loop can answer, each once. */
export function answerableQuestions(result: ClassificationResult): FollowUpQuestion[] {
  const byId = new Map(
    (result.follow_up_questions ?? [])
      .filter(isAnswerable)
      .map((question) => [question.id, question]),
  )
  return [...byId.values()]
}

/** The description with the answers a run used, one per line, for "Edit description": the user
 *  sees and keeps what they answered when they rewrite it (decision 019 appends them too). */
export function withAnswers(description: string, answers: Answers | undefined): string {
  const lines = Object.values(answers ?? {})
  return lines.length === 0 ? description : [description, '', ...lines].join('\n')
}

/** One answer as the engine reads it, or null when the draft says nothing (Not sure, blank
 *  words): a question without an answer is read as "don't know" (decision 019). A choice keeps
 *  its question, so the line says what it answers ("Is it used in the EU? Yes."). */
export function answerText(
  t: TFunction,
  question: FollowUpQuestion,
  draft: AnswerDraft | undefined,
): string | null {
  if (!draft) return null
  if (draft.option === 'yes' || draft.option === 'no') {
    const line = t('followUp.answerLine', {
      question: question.text,
      answer: t(`followUp.option.${draft.option}`),
    })
    return line.slice(0, MAX_ANSWER_CHARS)
  }
  const words = draft.text?.trim() ?? ''
  return words === '' ? null : words.slice(0, MAX_ANSWER_CHARS)
}

/** The drafts as answers, by question id, for the questions given. */
export function answersOf(
  t: TFunction,
  questions: readonly FollowUpQuestion[],
  drafts: AnswerDrafts,
): Answers {
  const entries = questions
    .filter(isAnswerable)
    .map((question) => [question.id, answerText(t, question, drafts[question.id])] as const)
    .filter((entry): entry is readonly [string, string] => entry[1] !== null)
  return Object.fromEntries(entries)
}

/** The answers a re-run sends: the earlier ones, with the new ones replacing any for the same
 *  question. Nothing beyond the API's cap is sent; the newest answers are kept. */
export function mergeAnswers(earlier: Answers | undefined, next: Answers): Answers {
  const merged = Object.entries({ ...earlier, ...next })
  const kept = merged.slice(Math.max(0, merged.length - MAX_ANSWERS))
  return Object.fromEntries(kept)
}

/** The facts a result rests on that Klar assumed: each card offers Confirm. */
export function assumedFacts(result: ClassificationResult): string[] {
  return restingFacts(result)
    .filter((fact) => fact.evidence === 'assumed')
    .map((fact) => fact.text)
}

/** The assumed fact a question asks the user to confirm (the engine's "Please confirm: <fact>",
 *  answered Yes or No), if it is one of `facts`. */
export function confirmedFact(question: FollowUpQuestion, facts: readonly string[]): string | null {
  if (!isAnswerable(question) || !optionsOf(question).includes('yes')) return null
  return facts.find((fact) => question.text.endsWith(fact)) ?? null
}

/** The questions a result's screen asks: the one that decides a paused result, and the others
 *  in the questions panel. A question confirming an assumed fact isn't asked there: its fact
 *  card's Confirm answers it, so each fact has one control. */
export function askedQuestions(result: ClassificationResult): {
  deciding: FollowUpQuestion | null
  others: FollowUpQuestion[]
} {
  const deciding =
    result.status === 'needs_more_information' ? (pausedStep(result)?.missing_fact ?? null) : null
  const facts = assumedFacts(result)
  const others = answerableQuestions(result).filter(
    (question) => question.id !== deciding?.id && confirmedFact(question, facts) === null,
  )
  return { deciding, others }
}

/** The id of a fact the user confirmed that no question asked about. */
export const CONFIRMED_PREFIX = 'confirmed_fact_'

/** Confirm on an assumed fact (user, 2026-10-07): Yes to the engine's own "Please confirm:
 *  <fact>" question when it asked one; otherwise the fact as the user's statement, under the
 *  next free `confirmed_fact_N` id, so an earlier confirmation is never replaced. */
export function confirmation(
  t: TFunction,
  questions: readonly FollowUpQuestion[],
  earlier: Answers | undefined,
  fact: string,
): Answers {
  const asked = questions.find((question) => confirmedFact(question, [fact]) !== null)
  const yes = asked && answerText(t, asked, { option: 'yes' })
  if (asked && yes) return { [asked.id]: yes }
  const taken = Object.keys(earlier ?? {}).filter((id) => id.startsWith(CONFIRMED_PREFIX)).length
  const text = t('followUp.confirmedLine', { fact }).slice(0, MAX_ANSWER_CHARS)
  return { [`${CONFIRMED_PREFIX}${String(taken + 1)}`]: text }
}

/** Whether the company profile places the company or its use in the EU (Art. 2(1)). */
function isEuFromProfile(profile: CompanyProfile | null): boolean {
  if (!profile) return false
  if (profile.usedIn !== null) return true
  return profile.establishedIn !== null && EU_MEMBER_STATES.has(profile.establishedIn)
}

/** The answers the company profile gives (decision 026 item 2): Yes to the EU question when the
 *  profile says the tools are used in the EU or the company is established there, unless the user
 *  chose to answer it themselves (`changed`). The screen shows them apart from the open questions
 *  (story P29); they are sent only when the user runs the checks again, with the other answers.
 *  The profile itself never reaches the engine (decision 026 item 7). */
export function profileDrafts(
  questions: readonly FollowUpQuestion[],
  profile: CompanyProfile | null,
  changed: ReadonlySet<string> = new Set(),
): AnswerDrafts {
  const asked = questions.some((question) => question.id === EU_LINK)
  if (!asked || changed.has(EU_LINK) || !isEuFromProfile(profile)) return {}
  return { [EU_LINK]: { option: 'yes' } }
}
