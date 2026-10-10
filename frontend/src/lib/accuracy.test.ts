import { describe, expect, it } from 'vitest'

import { parseSiteAccuracy, SITE_ACCURACY } from './accuracy'

const FIGURE = { value: 0.874, run_id: 'run-2026-11-02-a' }

describe('the site accuracy file', () => {
  it('holds no figure until the benchmark publishes them (P27)', () => {
    expect(SITE_ACCURACY).toEqual({
      risk_class_accuracy: null,
      false_low_risk_rate: null,
      citations_exist: null,
      head_to_head: null,
    })
  })

  it('takes measured figures with their run ids', () => {
    const figures = {
      risk_class_accuracy: FIGURE,
      false_low_risk_rate: { value: 0.031, run_id: 'run-2026-11-02-a' },
      citations_exist: { value: 1, run_id: 'run-2026-11-02-b' },
      head_to_head: { klar: FIGURE, checker: FIGURE, checker_name: 'Checker', cases: 120 },
    }
    expect(parseSiteAccuracy(figures)).toEqual(figures)
  })

  it.each([
    ['a rate above 1', { value: 87.4, run_id: 'run-a' }],
    ['a figure without its run', { value: 0.5 }],
    ['an empty run id', { value: 0.5, run_id: '' }],
  ])('rejects %s', (_, figure) => {
    expect(() => parseSiteAccuracy({ ...SITE_ACCURACY, risk_class_accuracy: figure })).toThrow()
  })

  it('rejects a file with a figure missing', () => {
    expect(() => parseSiteAccuracy({ risk_class_accuracy: null })).toThrow()
  })
})
