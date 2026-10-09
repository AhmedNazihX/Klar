import { describe, expect, it } from 'vitest'

import { providerRefused, storedBeforeDecision030, WORKED_EXAMPLE } from '@/test/classify-fixtures'

import { hasAssessedClass, riskClassOf } from './risk-class'

describe('riskClassOf', () => {
  it("gives a classified result's class", () => {
    expect(riskClassOf(WORKED_EXAMPLE)).toBe('high_risk')
  })

  it('refuses a needs-a-description result, which has no class to show', () => {
    expect(() => riskClassOf({ ...WORKED_EXAMPLE, steps: [], risk_class: null })).toThrow(
      'no class to show',
    )
  })

  it('refuses a result stored before decision 030 with a check not assessed', () => {
    expect(() => riskClassOf(storedBeforeDecision030())).toThrow('no class to show')
  })
})

describe('hasAssessedClass', () => {
  it('holds for a result with a class and every check assessed', () => {
    expect(hasAssessedClass(WORKED_EXAMPLE)).toBe(true)
    expect(hasAssessedClass({ ...WORKED_EXAMPLE, not_assessed: [] })).toBe(true)
  })

  it('fails for a result with no class, or one whose class rests on a check not assessed', () => {
    expect(hasAssessedClass(providerRefused())).toBe(false)
    const stored = storedBeforeDecision030()
    expect(stored.risk_class).toBe('high_risk')
    expect(hasAssessedClass(stored)).toBe(false)
  })
})
