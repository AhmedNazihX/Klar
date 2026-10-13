import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import type { ClassificationResult, FollowUpQuestion } from '@/api'
import { decidedHighRisk } from '@/test/classify-fixtures'

import { DescriptionFormSchema } from './description-form'

import {
  answerableQuestions,
  answersOf,
  askedQuestions,
  answerText,
  confirmation,
  MAX_ANSWER_CHARS,
  MAX_ANSWERS,
  mergeAnswers,
  optionsOf,
  withAnswers,
} from './follow-up-answers'

const YES_NO: FollowUpQuestion = {
  id: 'human_review',
  text: 'Does a person review it?',
  options: ['yes', 'no', 'not_sure'],
}
const WORDS: FollowUpQuestion = { id: 'ai_system', text: 'How does it work?', options: [] }

describe('the answers the engine reads', () => {
  it('pins the API caps: 40 answers of 1000 characters (ClassifyRequest)', () => {
    expect(MAX_ANSWERS).toBe(40)
    expect(MAX_ANSWER_CHARS).toBe(1000)
  })

  it('keeps the question with a choice, and leaves Not sure and blank words out', () => {
    const t = i18n.getFixedT('en')
    expect(answerText(t, YES_NO, { option: 'yes' })).toBe('Does a person review it? Yes.')
    expect(answerText(t, YES_NO, { option: 'no' })).toBe('Does a person review it? No.')
    expect(answerText(t, YES_NO, { option: 'not_sure' })).toBeNull()
    expect(answerText(t, WORDS, { text: '   ' })).toBeNull()
    expect(answerText(t, WORDS, undefined)).toBeNull()
    expect(answerText(i18n.getFixedT('de'), YES_NO, { option: 'no' })).toBe(
      'Does a person review it? Nein.',
    )
  })

  it('cuts an answer to the API cap', () => {
    const t = i18n.getFixedT('en')
    expect(answerText(t, WORDS, { text: 'x'.repeat(1500) })).toHaveLength(1000)
    const long = { ...YES_NO, text: 'q'.repeat(1200) }
    expect(answerText(t, long, { option: 'yes' })).toHaveLength(1000)
  })

  it('sends only questions with an id the API takes', () => {
    const t = i18n.getFixedT('en')
    const bad: FollowUpQuestion = { ...YES_NO, id: 'Not An Id' }
    expect(
      answersOf(t, [bad, YES_NO], {
        'Not An Id': { option: 'yes' },
        human_review: { option: 'no' },
      }),
    ).toEqual({
      human_review: 'Does a person review it? No.',
    })
    const result: ClassificationResult = {
      ...decidedHighRisk(),
      follow_up_questions: [bad, YES_NO, { ...YES_NO, text: 'Asked twice' }],
    }
    expect(answerableQuestions(result)).toEqual([{ ...YES_NO, text: 'Asked twice' }])
  })

  it('offers only the options it knows, in order', () => {
    expect(optionsOf({ ...YES_NO, options: ['not_sure', 'yes'] })).toEqual(['yes', 'not_sure'])
    expect(optionsOf(WORDS)).toEqual([])
  })
})

describe('merging answers', () => {
  it('replaces an earlier answer to the same question and keeps the others', () => {
    expect(mergeAnswers({ a: '1', b: '2' }, { b: '3', c: '4' })).toEqual({ a: '1', b: '3', c: '4' })
    expect(mergeAnswers(undefined, { a: '1' })).toEqual({ a: '1' })
  })

  it('keeps the newest 40 answers', () => {
    const earlier = Object.fromEntries(
      Array.from({ length: 40 }, (_, i) => [`q_${String(i)}`, 'x']),
    )
    const merged = mergeAnswers(earlier, { newest: 'y' })
    expect(Object.keys(merged)).toHaveLength(40)
    expect(merged).toHaveProperty('newest', 'y')
    expect(merged).not.toHaveProperty('q_0')
  })
})

describe('confirming a fact', () => {
  it('numbers its own confirmations so none replaces another', () => {
    const t = i18n.getFixedT('en')
    expect(confirmation(t, [], undefined, 'It ranks people.')).toEqual({
      confirmed_fact_1: 'Confirmed: It ranks people.',
    })
    expect(confirmation(t, [], { confirmed_fact_1: 'x' }, 'It ranks people.')).toEqual({
      confirmed_fact_2: 'Confirmed: It ranks people.',
    })
  })

  it("answers Yes to the engine's question about the fact when there is one", () => {
    const t = i18n.getFixedT('en')
    const asked: FollowUpQuestion = {
      id: 'confirm_it_ranks_people',
      text: 'Please confirm: It ranks people.',
      options: ['yes', 'no', 'not_sure'],
    }
    expect(confirmation(t, [WORDS, asked], undefined, 'It ranks people.')).toEqual({
      confirm_it_ranks_people: 'Please confirm: It ranks people. Yes.',
    })
  })
})

describe('Edit description', () => {
  it('puts the answers under the description, one per line', () => {
    expect(withAnswers('We use a tool.', { a: 'One. Yes.', b: 'Two.' })).toEqual({
      text: 'We use a tool.\n\nOne. Yes.\nTwo.',
      hasDroppedAnswers: false,
    })
    const alone = { text: 'We use a tool.', hasDroppedAnswers: false }
    expect(withAnswers('We use a tool.', {})).toEqual(alone)
    expect(withAnswers('We use a tool.', undefined)).toEqual(alone)
  })

  it('keeps whole answers within the form’s 20,000 characters and says when one is left out', () => {
    const description = 'd'.repeat(19_970)
    // 19,970 + 2 + 20 = 19,992 fits; the next answer, 1 + 9 more, would make 20,002.
    const fits = 'a'.repeat(20)
    const edited = withAnswers(description, { a: fits, b: 'b'.repeat(9), c: 'c' })
    expect(edited).toEqual({ text: `${description}\n\n${fits}`, hasDroppedAnswers: true })
    expect(DescriptionFormSchema.safeParse({ name: '', description: edited.text }).success).toBe(
      true,
    )
    // Exactly at the limit, nothing is left out.
    const exact = withAnswers(description, { a: 'a'.repeat(28) })
    expect(exact.text).toHaveLength(20_000)
    expect(exact.hasDroppedAnswers).toBe(false)
  })

  it('opens with the description alone when no answer fits', () => {
    const description = 'd'.repeat(19_999)
    expect(withAnswers(description, { a: 'Yes.' })).toEqual({
      text: description,
      hasDroppedAnswers: true,
    })
  })

  it('leaves out an answer one character too long, and keeps one that fits exactly', () => {
    const description = 'd'.repeat(19_970)
    // 19,970 + 2 + 29 = 20,001: one over.
    expect(withAnswers(description, { a: 'a'.repeat(29) })).toEqual({
      text: description,
      hasDroppedAnswers: true,
    })
    // 19,970 + 2 + 28 = 20,000: exactly at the limit.
    const exact = withAnswers(description, { a: 'a'.repeat(28) })
    expect(exact).toEqual({ text: `${description}\n\n${'a'.repeat(28)}`, hasDroppedAnswers: false })
    expect(exact.text).toHaveLength(20_000)
  })

  it('cuts a description over the limit on its own, and leaves every answer out', () => {
    const description = 'd'.repeat(20_000) + 'e'.repeat(50)
    expect(withAnswers(description, undefined)).toEqual({
      text: 'd'.repeat(20_000),
      hasDroppedAnswers: false,
    })
    expect(withAnswers(description, { a: 'Yes.' })).toEqual({
      text: 'd'.repeat(20_000),
      hasDroppedAnswers: true,
    })
  })

  it.each([0, 1_000, 18_000, 19_000, 19_998, 19_999, 20_000, 25_000])(
    'never opens with more than 20,000 characters (a description of %i)',
    (length) => {
      // 40 answers of 1,000 characters each, the API's most.
      const answers = Object.fromEntries(
        Array.from({ length: 40 }, (_, index) => [`q${String(index)}`, 'a'.repeat(1_000)]),
      )
      expect(withAnswers('d'.repeat(length), answers).text.length).toBeLessThanOrEqual(20_000)
    },
  )
})

describe('the questions a result asks', () => {
  const assumed = 'The company bought the tool.'
  const inferred = 'It ranks applicants.'
  const confirmAssumed: FollowUpQuestion = {
    id: 'confirm_the_company_bought_the_tool',
    text: `Please confirm: ${assumed}`,
    options: ['yes', 'no', 'not_sure'],
  }
  const confirmInferred: FollowUpQuestion = {
    id: 'confirm_it_ranks_applicants',
    text: `Please confirm: ${inferred}`,
    options: ['yes', 'no', 'not_sure'],
  }

  it("leaves an assumed fact's question to its card, and asks the rest", () => {
    const result: ClassificationResult = {
      ...decidedHighRisk(),
      deciding_facts: [
        { text: assumed, evidence: 'assumed' },
        { text: inferred, evidence: 'inferred' },
      ],
      follow_up_questions: [confirmAssumed, confirmInferred, YES_NO],
    }
    const { deciding, others } = askedQuestions(result)
    expect(deciding).toBeNull()
    // An inferred fact's card has no Confirm, so its question stays in the panel.
    expect(others.map((question) => question.id)).toEqual([confirmInferred.id, YES_NO.id])
  })

  it("asks a paused result's deciding question once, apart from the others", () => {
    const result: ClassificationResult = {
      ...decidedHighRisk(),
      status: 'needs_more_information',
      follow_up_questions: [YES_NO, WORDS],
      steps: decidedHighRisk().steps.map((step) =>
        step.step === 'scope'
          ? { ...step, status: 'needs_more_information', missing_fact: WORDS }
          : step,
      ),
    }
    const { deciding, others } = askedQuestions(result)
    expect(deciding?.id).toBe(WORDS.id)
    expect(others.map((question) => question.id)).toEqual([YES_NO.id])
  })
})
