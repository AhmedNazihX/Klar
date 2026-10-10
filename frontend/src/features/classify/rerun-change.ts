import i18n, { type TFunction } from 'i18next'

import type { ClassificationResult, FollowUpQuestion } from '@/api'
import { ambiguousProvision } from '@/features/inventory/tool-facts'
import { SUPPORTED_LANGUAGES, type Language } from '@/i18n'
import { riskClassOf } from '@/lib/risk-class'
import type { Answers } from '@/lib/tool-runs'

import { askedQuestions, assumedFacts, CONFIRMED_PREFIX, confirmedFact } from './follow-up-answers'
import { provisionName } from './provision-names'

// What a follow-up re-run changed (artboard `ResultRerun`): the class before and after, the
// answers the user gave, and the lines the Inventory, Obligations and "needs you" lists show for
// the tool, in the words those screens use. An assumed result keeps its stricter class and says
// so (it never looks settled).

/** Whether the answer changed the class or whether it is settled. */
export function hasResultChanged(
  before: ClassificationResult,
  after: ClassificationResult,
): boolean {
  return before.risk_class !== after.risk_class || before.status !== after.status
}

/** The class as the inventory's pill shows it: "High-risk", or "High-risk, assumed". */
export function classLabel(t: TFunction, result: ClassificationResult): string {
  const name = t(`pill.${riskClassOf(result)}`)
  return result.status === 'decided' ? name : t('inventory.table.assumedClass', { riskClass: name })
}

/** The tool's line in the obligations list: its duties, "possible" while the result is assumed. */
export function dutiesLabel(t: TFunction, result: ClassificationResult): string {
  const count = (result.obligations ?? []).filter((duty) => !duty.is_informational).length
  if (count === 0) return t('followUp.lists.noDuties')
  return result.status === 'decided'
    ? t('followUp.lists.duties', { count })
    : t('followUp.lists.possibleDuties', { count })
}

/** What the tool needs from the user. A paused result counts the questions its screen asked
 *  (the deciding one and the questions panel), so the line agrees with what the user saw. */
export function needsLabel(t: TFunction, result: ClassificationResult, language: Language): string {
  if (result.risk_class === 'prohibited') return t('inventory.needs.prohibited')
  if (result.status === 'needs_more_information') {
    const { deciding, others } = askedQuestions(result)
    const count = Math.max(1, others.length + (deciding ? 1 : 0))
    return t('followUp.lists.answer', { count })
  }
  if (result.status === 'legally_ambiguous') {
    const provision = ambiguousProvision(result)
    return provision
      ? t('inventory.needs.ambiguous', { provision: provisionName(provision, language) })
      : t('inventory.needs.ambiguousPlain')
  }
  return t('followUp.lists.nothing')
}

/** Every question a result asked, by id: its follow-up questions and its steps' missing facts. */
function questionsById(result: ClassificationResult): Map<string, FollowUpQuestion> {
  const missing = result.steps.flatMap((step) => (step.missing_fact ? [step.missing_fact] : []))
  return new Map(
    [...missing, ...(result.follow_up_questions ?? [])].map((question) => [question.id, question]),
  )
}

// An answer keeps the words of the language it was given in, which may not be the screen's now,
// so these read it in every language the app has.

/** "Yes" in every language. */
function yesLabels(): string[] {
  return SUPPORTED_LANGUAGES.map((lng) => i18n.t('followUp.option.yes', { lng }))
}

/** The fact in a "Confirmed: <fact>" line, in whichever language it was written. */
function confirmedLineFact(line: string): string {
  const MARK = '\u0000'
  const templates = SUPPORTED_LANGUAGES.map((lng) =>
    i18n.t('followUp.confirmedLine', { lng, fact: MARK }),
  )
  for (const template of templates) {
    const [before = '', after = ''] = template.split(MARK)
    if (line.startsWith(before) && line.endsWith(after)) {
      return line.slice(before.length, line.length - after.length)
    }
  }
  return line
}

/** One answer as the user gave it: the fact they confirmed, or the question and their choice or
 *  words. The line the engine read ("<question> No.") is never shown as theirs. */
function saidLine(
  t: TFunction,
  [id, line]: readonly [string, string],
  asked: ReadonlyMap<string, FollowUpQuestion>,
  facts: readonly string[],
): string {
  if (id.startsWith(CONFIRMED_PREFIX)) {
    return t('followUp.banner.youConfirmed', { fact: confirmedLineFact(line) })
  }
  const question = asked.get(id)
  if (!question) return t('followUp.banner.youSaid', { answer: line })
  const lead = `${question.text} `
  const choice = line.startsWith(lead) ? line.slice(lead.length).replace(/\.$/, '') : null
  const fact = confirmedFact(question, facts)
  if (fact !== null && choice !== null && yesLabels().includes(choice)) {
    return t('followUp.banner.youConfirmed', { fact })
  }
  return t('followUp.banner.youSaidTo', { question: question.text, answer: choice ?? line })
}

/** The answers this run added or changed since the run before, as the user gave them. */
export function newAnswers(
  t: TFunction,
  previous: ClassificationResult,
  answers: Answers | undefined,
  before: Answers,
): string[] {
  const asked = questionsById(previous)
  const facts = assumedFacts(previous)
  return Object.entries(answers ?? {})
    .filter(([id, text]) => before[id] !== text)
    .map((entry) => saidLine(t, entry, asked, facts))
}
