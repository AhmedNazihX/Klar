import { describe, expect, it } from 'vitest'

import type { Citation, ClassificationResult } from '@/api'
import { RECORDED_PROHIBITED } from '@/test/prohibited-fixtures'

import { bannedSince, banPoints, isDecidedBan } from './ban'

function cite(provisionId: string): Citation {
  return {
    provision_id: provisionId,
    document_id: 'ai-act-consolidated',
    language: 'en',
    quote: 'q',
  }
}

function citing(...ids: string[]): ClassificationResult {
  return {
    ...RECORDED_PROHIBITED,
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
    expect(banPoints(citing(...ids, 'art:5:1:ba'))).toEqual(['art:5:1:ba'])
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
