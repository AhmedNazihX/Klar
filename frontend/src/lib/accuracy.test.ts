import { describe, expect, it } from 'vitest'

import { parseSiteAccuracy, SITE_ACCURACY } from './accuracy'

const FIGURE = { value: 0.874, run_id: 'run-2026-11-02-a' }

describe('the site accuracy file', () => {
  it('holds the measured figures, each naming its run (P27)', () => {
    const { risk_class_accuracy, false_low_risk_rate, citations_exist, head_to_head } =
      SITE_ACCURACY
    const figures = [
      risk_class_accuracy,
      false_low_risk_rate,
      citations_exist,
      head_to_head?.klar,
      head_to_head?.checker,
    ]
    for (const figure of figures) expect(figure?.run_id).toMatch(/^[0-9a-f-]{36}$/)
    expect(head_to_head?.cases).toBeGreaterThan(0)
  })

  it('takes measured figures with their run ids', () => {
    const figures = {
      risk_class_accuracy: FIGURE,
      false_low_risk_rate: { value: 0.031, run_id: 'run-2026-11-02-a' },
      citations_exist: { value: 1, run_id: 'run-2026-11-02-b' },
      head_to_head: { klar: FIGURE, checker: FIGURE, checker_name: 'Checker', cases: 120 },
      scored_cases: { count: 152, run_id: 'run-2026-11-02-a' },
      own_cases: { count: 88, run_id: 'run-2026-11-02-c' },
      run_date: '2026-11-02',
      report: 'eval/reports/final.md',
      run_ids: ['run-2026-11-02-a', 'run-2026-11-02-b'],
      note: 'Run a, the user’s choice.',
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
