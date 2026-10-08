import { describe, expect, it } from 'vitest'

import type { CheckedDraft } from '@/api'
import {
  DEPLOYER_DOCUMENTS,
  LIMITED_DOCUMENTS,
  PROVIDER_DOCUMENTS,
} from '@/test/documents-fixtures'

import { interviewState, isAnswered, isSkeleton, unansweredCount, withoutBlank } from './interview'

function draft(drafts: Readonly<Record<string, CheckedDraft>>, template: string): CheckedDraft {
  const found = drafts[template]
  if (!found) throw new Error(`no ${template} in the fixture`)
  return found
}

const WORKERS = draft(DEPLOYER_DOCUMENTS.en, 'art_26_7_workers')
const ANNEX_IV = draft(PROVIDER_DOCUMENTS.en, 'annex_iv_technical_documentation')
const ART_50_3 = draft(LIMITED_DOCUMENTS.en, 'art_50_3_disclosure')
const NONE = new Set<string>()

function keys(questions: readonly { key: string }[]): string[] {
  return questions.map((question) => question.key)
}

describe('The guided interview', () => {
  it('asks the first unanswered question, and a blank answer counts as unanswered', () => {
    const state = interviewState(WORKERS.questions, false, { recipients: '   ' }, NONE, null)
    expect(state.current?.key).toBe('recipients')
    expect(state.section).toBeNull()
    expect(keys(state.answered)).toEqual([])
    expect(keys(state.upcoming)).toEqual(['tool_and_supplier', 'start_date', 'reviewer'])
  })

  it('moves past a skipped question and comes back to a chosen one', () => {
    const answers = { tool_and_supplier: 'TalentRank.' }
    const skipped = interviewState(WORKERS.questions, false, answers, new Set(['recipients']), null)
    expect(skipped.current?.key).toBe('start_date')
    expect(keys(skipped.answered)).toEqual(['tool_and_supplier'])
    const chosen = interviewState(
      WORKERS.questions,
      false,
      answers,
      new Set(['recipients']),
      'tool_and_supplier',
    )
    expect(chosen.current?.key).toBe('tool_and_supplier')
  })

  it('ends when every question is answered or skipped', () => {
    const state = interviewState(
      WORKERS.questions,
      false,
      {},
      new Set(keys(WORKERS.questions)),
      null,
    )
    expect(state.current).toBeNull()
    expect(keys(state.upcoming)).toEqual(keys(WORKERS.questions))
  })

  it("keeps a skeleton's interview to the section of the question asked", () => {
    expect(isSkeleton(ANNEX_IV)).toBe(true)
    expect(isSkeleton(WORKERS)).toBe(false)
    const general = ANNEX_IV.questions.filter((q) => q.section === 'general_description')
    const answers = Object.fromEntries(general.map((q) => [q.key, 'Given.']))
    const state = interviewState(ANNEX_IV.questions, true, answers, NONE, null)
    expect(state.section).toBe('development')
    expect(state.questions.length).toBeGreaterThan(0)
    expect(state.questions.every((q) => q.section === 'development')).toBe(true)
    expect(state.answered).toEqual([])
  })
})

describe('What a document still needs', () => {
  const [choice] = ART_50_3.questions

  it('counts a choice question answered only by one of its choices, as the drafter does', () => {
    if (!choice) throw new Error('the Art. 50(3) disclosure asks a choice first')
    expect(choice.choices?.map((option) => option.key)).toEqual([
      'emotion_recognition',
      'biometric_categorisation',
      'both',
    ])
    expect(isAnswered({ recognises: 'both' }, choice)).toBe(true)
    expect(isAnswered({ recognises: ' both ' }, choice)).toBe(true)
    expect(isAnswered({ recognises: 'Both!' }, choice)).toBe(false)
    expect(isAnswered({ recognises: 'BOTH' }, choice)).toBe(false)
    expect(isAnswered({ recognises: '\ufeffboth\x85' }, choice)).toBe(true)
    expect(isAnswered({}, choice)).toBe(false)
  })

  it('reads blank as the drafter does: whitespace and the byte order mark, nothing else', () => {
    const [first] = WORKERS.questions
    if (!first) throw new Error('the workers notice asks questions')
    for (const blank of ['\ufeff', ' \x1c\x85\u3000\ufeff ']) {
      expect(isAnswered({ [first.key]: blank }, first)).toBe(false)
    }
    expect(unansweredCount(WORKERS.questions, { [first.key]: '\ufeff' })).toBe(
      WORKERS.document.unanswered,
    )
    expect(withoutBlank('\ufeff Rank GmbH\x1f')).toBe('Rank GmbH')
    expect(withoutBlank('Rank GmbH\u200b')).toBe('Rank GmbH\u200b')
  })

  it('counts the questions left, as the drafted document does', () => {
    expect(unansweredCount(WORKERS.questions, {})).toBe(WORKERS.document.unanswered)
    const answered = draft(DEPLOYER_DOCUMENTS.en_answered, 'art_26_7_workers')
    expect(unansweredCount(answered.questions, { tool_and_supplier: 'TalentRank.' })).toBe(
      answered.document.unanswered,
    )
    const chosen = draft(LIMITED_DOCUMENTS.en_answered, 'art_50_3_disclosure')
    expect(unansweredCount(chosen.questions, { recognises: 'both' })).toBe(
      chosen.document.unanswered,
    )
  })
})
