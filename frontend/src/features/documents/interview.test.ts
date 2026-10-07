import { describe, expect, it } from 'vitest'

import type { CheckedDraft } from '@/api'
import { DEPLOYER_DRAFTS, PROVIDER_DRAFTS } from '@/test/documents-fixtures'

import { interviewState, isSkeleton } from './interview'

function draft(drafts: readonly CheckedDraft[], template: string): CheckedDraft {
  const found = drafts.find((item) => item.document.template === template)
  if (!found) throw new Error(`no ${template} in the fixture`)
  return found
}

const WORKERS = draft(DEPLOYER_DRAFTS.en, 'art_26_7_workers')
const ANNEX_IV = draft(PROVIDER_DRAFTS.en, 'annex_iv_technical_documentation')
const NONE = new Set<string>()

function keys(questions: readonly { key: string }[]): string[] {
  return questions.map((question) => question.key)
}

describe('The guided interview', () => {
  it('asks the first unanswered question, and a blank answer counts as unanswered', () => {
    const state = interviewState(WORKERS, { recipients: '   ' }, NONE, null)
    expect(state.current?.key).toBe('recipients')
    expect(state.section).toBeNull()
    expect(keys(state.answered)).toEqual([])
    expect(keys(state.upcoming)).toEqual(['tool_and_supplier', 'start_date', 'reviewer'])
  })

  it('moves past a skipped question and comes back to a chosen one', () => {
    const answers = { tool_and_supplier: 'TalentRank.' }
    const skipped = interviewState(WORKERS, answers, new Set(['recipients']), null)
    expect(skipped.current?.key).toBe('start_date')
    expect(keys(skipped.answered)).toEqual(['tool_and_supplier'])
    const chosen = interviewState(WORKERS, answers, new Set(['recipients']), 'tool_and_supplier')
    expect(chosen.current?.key).toBe('tool_and_supplier')
  })

  it('ends when every question is answered or skipped', () => {
    const state = interviewState(WORKERS, {}, new Set(keys(WORKERS.questions)), null)
    expect(state.current).toBeNull()
    expect(keys(state.upcoming)).toEqual(keys(WORKERS.questions))
  })

  it("keeps a skeleton's interview to the section of the question asked", () => {
    expect(isSkeleton(ANNEX_IV)).toBe(true)
    expect(isSkeleton(WORKERS)).toBe(false)
    const general = ANNEX_IV.questions.filter((q) => q.section === 'general_description')
    const answers = Object.fromEntries(general.map((q) => [q.key, 'Given.']))
    const state = interviewState(ANNEX_IV, answers, NONE, null)
    expect(state.section).toBe('development')
    expect(state.questions.length).toBeGreaterThan(0)
    expect(state.questions.every((q) => q.section === 'development')).toBe(true)
    expect(state.answered).toEqual([])
  })
})
