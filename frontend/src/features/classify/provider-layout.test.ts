import { describe, expect, it } from 'vitest'

import type { ClassificationResult } from '@/api'
import { decidedHighRisk, limitedRiskProvider } from '@/test/classify-fixtures'
import {
  GPAI_HIGH_RISK,
  OWN_BRAND_PROVIDER,
  ownBrandCiting,
  PROVIDER_ALSO_DEPLOYER,
} from '@/test/provider-fixtures'

import {
  groupDuties,
  internalControlPoint,
  isGpaiBased,
  isProviderLayout,
  providerReason,
  simplifiedFormFor,
} from './provider-layout'

function withPoint(annexPoint: string | null): ClassificationResult {
  return { ...OWN_BRAND_PROVIDER, annex_point: annexPoint }
}

describe('isProviderLayout', () => {
  it('takes a high-risk result for a provider only', () => {
    expect(isProviderLayout(OWN_BRAND_PROVIDER)).toBe(true)
    expect(isProviderLayout(decidedHighRisk())).toBe(false)
    expect(isProviderLayout(limitedRiskProvider())).toBe(false)
  })

  it('leaves a legally ambiguous result to the ambiguous layout (P22)', () => {
    expect(isProviderLayout({ ...OWN_BRAND_PROVIDER, status: 'needs_more_information' })).toBe(true)
    expect(isProviderLayout({ ...OWN_BRAND_PROVIDER, status: 'legally_ambiguous' })).toBe(false)
  })
})

describe('internalControlPoint (Art. 43(2))', () => {
  it.each([
    ['annex:III:2:a', '2'],
    ['annex:III:4:b', '4'],
    ['annex:III:5:a', '5'],
    ['annex:III:8:a', '8'],
  ])('names the point for %s', (point, expected) => {
    expect(internalControlPoint(withPoint(point))).toBe(expected)
  })

  it.each([['annex:III:1:a'], ['annex:I:A:11'], [null]])('has none for %s', (point) => {
    expect(internalControlPoint(withPoint(point))).toBeNull()
  })
})

describe('simplifiedFormFor (Art. 11(1))', () => {
  it.each([
    ['sme', 'amended', 'sme'],
    ['sme', 'original', 'sme'],
    ['smc', 'amended', 'smc'],
    ['smc', 'original', null],
    ['none', 'amended', null],
    [null, 'amended', null],
    [undefined, 'amended', null],
  ] as const)('%s under the %s text: %s', (sizeClass, shown, expected) => {
    expect(simplifiedFormFor(sizeClass, shown, OWN_BRAND_PROVIDER)).toBe(expected)
  })

  it('names no small mid-cap on a result run under the original text', () => {
    const original = { ...OWN_BRAND_PROVIDER, law_version: 'original' as const }
    expect(simplifiedFormFor('smc', 'amended', original)).toBeNull()
    expect(simplifiedFormFor('sme', 'amended', original)).toBe('sme')
  })
})

describe('isGpaiBased', () => {
  it('reads the role step citing Art. 3(68)', () => {
    expect(isGpaiBased(GPAI_HIGH_RISK)).toBe(true)
    expect(isGpaiBased(OWN_BRAND_PROVIDER)).toBe(false)
  })

  it('is false for a role other than provider', () => {
    expect(isGpaiBased({ ...GPAI_HIGH_RISK, role: 'deployer' })).toBe(false)
  })

  it("is false while a step's missing fact still asks it", () => {
    const steps = GPAI_HIGH_RISK.steps.map((step) =>
      step.step === 'role_obligations'
        ? {
            ...step,
            status: 'needs_more_information' as const,
            missing_fact: {
              id: 'builds_on_gpai',
              text: 'Built on a GPAI model?',
              about: 'art:3:68',
            },
          }
        : step,
    )
    expect(isGpaiBased({ ...GPAI_HIGH_RISK, steps })).toBe(false)
  })
})

describe('providerReason', () => {
  it.each([
    ['switch_a', OWN_BRAND_PROVIDER],
    ['switch_b', ownBrandCiting('art:3:7', 'art:25:1:b')],
    ['switch_c', PROVIDER_ALSO_DEPLOYER],
    // The engine cites every point that applies, in any order: the sentence names each one.
    ['switch_ab', ownBrandCiting('art:25:1:b', 'art:3:7', 'art:25:1:a')],
    ['switch_ac', ownBrandCiting('art:25:1:a', 'art:25:1:c')],
    ['switch_bc', ownBrandCiting('art:25:1:c', 'art:25:1:b')],
    ['switch_abc', ownBrandCiting('art:25:1:a', 'art:25:1:b', 'art:25:1:c')],
    ['own', { ...OWN_BRAND_PROVIDER, role_switch_reason: null }],
    ['gpai', GPAI_HIGH_RISK],
  ] as const)('is %s', (expected, result) => {
    expect(providerReason(result)).toBe(expected)
  })

  it('claims no reason for a switch whose role step cites no Art. 25(1) point', () => {
    expect(providerReason(ownBrandCiting('art:3:7'))).toBe('stated')
  })

  it('claims no reason when the role step did not settle the role', () => {
    const steps = OWN_BRAND_PROVIDER.steps.map((step) =>
      step.step === 'role_obligations' ? { ...step, status: 'legally_ambiguous' as const } : step,
    )
    expect(providerReason({ ...OWN_BRAND_PROVIDER, role_switch_reason: null, steps })).toBe(
      'stated',
    )
  })
})

describe('groupDuties', () => {
  it("puts each provider duty in its group and the deployer's apart", () => {
    const groups = groupDuties(PROVIDER_ALSO_DEPLOYER.obligations ?? [])
    expect(groups.build.map((duty) => duty.article)).toContain('art:9')
    expect(groups.prove.map((duty) => duty.article)).toContain('art:11:1')
    expect(groups.after_launch.map((duty) => duty.article)).toContain('art:73:1')
    expect(groups.other.map((duty) => duty.article)).toEqual([
      'art:26:1',
      'art:26:2',
      'art:26:4',
      'art:26:5',
      'art:26:6',
      'art:26:7',
      'art:26:8',
      'art:26:9',
      'art:26:11',
      'art:26:12',
      'art:27:1',
      'art:86:1',
    ])
  })
})
