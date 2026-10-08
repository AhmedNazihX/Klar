import { describe, expect, it } from 'vitest'

import { WORKED_EXAMPLE } from '@/test/classify-fixtures'

import { riskClassOf } from './risk-class'

describe('riskClassOf', () => {
  it("gives a classified result's class", () => {
    expect(riskClassOf(WORKED_EXAMPLE)).toBe('high_risk')
  })

  it('refuses a needs-a-description result, which has no class to show', () => {
    expect(() => riskClassOf({ ...WORKED_EXAMPLE, steps: [], risk_class: null })).toThrow(
      'no class to show',
    )
  })
})
