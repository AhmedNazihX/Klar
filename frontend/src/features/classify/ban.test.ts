import { describe, expect, it } from 'vitest'

import type { Citation, ClassificationResult } from '@/api'
import { RECORDED_PROHIBITED } from '@/test/prohibited-fixtures'

import { bannedSince, banPoints, isDecidedBan, laterPoints } from './ban'

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

describe('laterPoints', () => {
  it('lists the cited points that apply only later, each once, with the day they start', () => {
    const result = citing('art:5:1:f', 'art:5:1:bb', 'art:5:1:ba', 'art:5:1:bb')
    expect(laterPoints(result)).toEqual([
      { point: 'art:5:1:bb', appliesFrom: '2026-12-02' },
      { point: 'art:5:1:ba', appliesFrom: '2026-12-02' },
    ])
  })

  it.each([
    ['2026-12-01', [{ point: 'art:5:1:ba', appliesFrom: '2026-12-02' }]],
    ['2026-12-02', []],
  ])('on %s lists %j', (asOf, later) => {
    expect(laterPoints(citingOn(asOf, 'art:5:1:f', 'art:5:1:ba'))).toEqual(later)
  })

  it('lists nothing for a ban on points that already apply, sub-points and guidance', () => {
    const result = citing(
      'art:5:1:f',
      'art:5:1:c:i',
      'art:113:a',
      'guide:guide-prohibited:para:254',
    )
    expect(laterPoints(result)).toEqual([])
  })
})
