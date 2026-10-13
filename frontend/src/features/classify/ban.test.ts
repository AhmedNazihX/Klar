import { describe, expect, it } from 'vitest'

import type { Citation, ClassificationResult } from '@/api'
import { RECORDED_PROHIBITED } from '@/test/prohibited-fixtures'

import { banDecisionNote, bannedSince, banPoints, isDecidedBan } from './ban'

function cite(provisionId: string): Citation {
  return {
    provision_id: provisionId,
    document_id: 'ai-act-consolidated',
    language: 'en',
    quote: 'q',
  }
}

function citing(...ids: string[]): ClassificationResult {
  return citingOn(RECORDED_PROHIBITED.as_of, ...ids)
}

/** The recorded ban, dated `asOf`, its Art. 5 step citing `ids`. */
function citingOn(asOf: string, ...ids: string[]): ClassificationResult {
  return {
    ...RECORDED_PROHIBITED,
    as_of: asOf,
    steps: RECORDED_PROHIBITED.steps.map((step) =>
      step.step === 'prohibited' ? { ...step, citations: ids.map(cite) } : step,
    ),
  }
}

describe('isDecidedBan', () => {
  it('holds for the recorded decided ban', () => {
    expect(isDecidedBan(RECORDED_PROHIBITED)).toBe(true)
  })

  it.each<[string, Partial<ClassificationResult>]>([
    ['an assumed ban', { status: 'needs_more_information' }],
    ['a legally ambiguous ban', { status: 'legally_ambiguous' }],
    ['a high-risk result', { risk_class: 'high_risk' }],
    ['a refused check (decision 030)', { risk_class: null, not_assessed: ['prohibited'] }],
    ['a ban stored before decision 030 with a refused check', { not_assessed: ['transparency'] }],
  ])('does not hold for %s', (_, change) => {
    expect(isDecidedBan({ ...RECORDED_PROHIBITED, ...change })).toBe(false)
  })
})

describe('banPoints', () => {
  it('keeps each Art. 5(1) point once, in the order cited', () => {
    expect(banPoints(citing('art:5:1:f', 'art:5:1:c', 'art:5:1:f'))).toEqual([
      'art:5:1:f',
      'art:5:1:c',
    ])
  })

  it('leaves out sub-points, the Art. 5(1a) routes, other articles and guidance', () => {
    const ids = [
      'art:5:1:c:i',
      'art:5:1a',
      'art:5:1',
      'art:99:3',
      'guide:guide-prohibited:para:254',
    ]
    expect(banPoints(citing(...ids, 'art:5:1:f'))).toEqual(['art:5:1:f'])
  })

  it.each(['art:5:1:ba', 'art:5:1:bb'])(
    'leaves out %s while it applies only later (the recorded date, 30 September 2026)',
    (later) => {
      expect(RECORDED_PROHIBITED.as_of).toBe('2026-09-30')
      const result = citing('art:5:1:f', later)
      expect(banPoints(result)).toEqual(['art:5:1:f'])
      expect(bannedSince(banPoints(result))).toBe('2025-02-02')
    },
  )

  it.each([
    ['2026-12-01', ['art:5:1:f']],
    ['2026-12-02', ['art:5:1:f', 'art:5:1:ba']],
    ['2027-03-01', ['art:5:1:f', 'art:5:1:ba']],
  ])('on %s keeps the points that apply then: %j', (asOf, points) => {
    expect(banPoints(citingOn(asOf, 'art:5:1:f', 'art:5:1:ba'))).toEqual(points)
  })

  it('dates a ban that rests on (bb) alone from 2 December 2026, once it applies', () => {
    const result = citingOn('2026-12-05', 'art:5:1:bb')
    expect(banPoints(result)).toEqual(['art:5:1:bb'])
    expect(bannedSince(banPoints(result))).toBe('2026-12-02')
  })
})

describe('bannedSince', () => {
  it.each([
    [['art:5:1:f'], '2025-02-02'],
    [['art:5:1:ba'], '2026-12-02'],
    [['art:5:1:bb'], '2026-12-02'],
    [['art:5:1:ba', 'art:5:1:f'], '2025-02-02'],
    [[], '2025-02-02'],
  ])('dates the ban on %j from %s', (points, date) => {
    expect(bannedSince(points)).toBe(date)
  })
})

describe('banDecisionNote', () => {
  const fact = 'It infers staff mood from their voices on calls.'
  const later =
    'Art. 5(1)(ba) applies only from 2 December 2026 (Art. 113(a)), so on 30 September 2026 it ' +
    `does not yet prohibit this system; from 2 December 2026 it may apply: ${fact}`

  /** The recorded ban with its Art. 5 decision as `decision`, resting on `fact`. */
  function deciding(decision: string): ClassificationResult {
    const facts = [{ text: fact, evidence: 'stated' as const, source_span: null }]
    return {
      ...RECORDED_PROHIBITED,
      deciding_facts: facts,
      steps: RECORDED_PROHIBITED.steps.map((step) =>
        step.step === 'prohibited' ? { ...step, decision, facts_used: facts } : step,
      ),
    }
  }

  it('adds nothing for the recorded German ban: its point and its fact are shown beside it', () => {
    const step = RECORDED_PROHIBITED.steps.find((candidate) => candidate.step === 'prohibited')
    expect(step?.decision).toMatch(/^Verboten nach Art\. 5 Abs\. 1 Buchst\. f\. \S/)
    expect(banDecisionNote(RECORDED_PROHIBITED)).toBeNull()
  })

  it('adds nothing for an English ban on two points', () => {
    const decision = `Prohibited under Art. 5(1)(f), Art. 5(1)(g). ${fact}`
    expect(banDecisionNote(deciding(decision))).toBeNull()
  })

  it('keeps a later point’s sentence whole, its own fact included', () => {
    const decision = `Prohibited under Art. 5(1)(f). ${fact} ${later}`
    expect(banDecisionNote(deciding(decision))).toBe(later)
  })

  it('keeps a decision that doesn’t open with the ban, less the facts it starts with', () => {
    expect(banDecisionNote(deciding(`${fact} Something else.`))).toBe('Something else.')
  })
})
