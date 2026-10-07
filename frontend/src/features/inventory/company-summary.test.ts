import { describe, expect, it } from 'vitest'

import type { ClassificationResult } from '@/api'
import type { InventoryTool } from '@/lib/inventory'
import {
  decidedHighRisk,
  legacyMarkedDeployer,
  limitedRisk,
  limitedRiskProvider,
  minimalRisk,
  WORKED_EXAMPLE,
} from '@/test/classify-fixtures'
import { ambiguousResult, prohibitedResult, toolId } from '@/test/inventory-fixtures'

import {
  classCounts,
  nextDuties,
  sharedLawDate,
  toolsNeedingYou,
  transparencyInForce,
} from './company-summary'

const TODAY = new Date(2026, 9, 7)

function tool(name: string, result: ClassificationResult | null): InventoryTool {
  return {
    toolId: toolId(),
    name,
    description: name,
    createdAt: '2026-10-01T09:00:00+00:00',
    result,
    hasUnreadableResult: false,
  }
}

describe('classCounts', () => {
  it('counts each class, an assumed result in its stricter class and flagged as assumed', () => {
    const counts = classCounts([
      tool('Decided', decidedHighRisk()),
      tool('Paused', WORKED_EXAMPLE),
      tool('Ambiguous', ambiguousResult()),
      tool('Banned', prohibitedResult()),
      tool('Unchecked', null),
    ])
    expect(counts).toEqual([
      { riskClass: 'prohibited', total: 1, assumed: 0 },
      { riskClass: 'high_risk', total: 3, assumed: 2 },
      { riskClass: 'limited_risk', total: 0, assumed: 0 },
      { riskClass: 'minimal_risk', total: 0, assumed: 0 },
      { riskClass: 'out_of_scope', total: 0, assumed: 0 },
    ])
  })
})

describe('toolsNeedingYou', () => {
  it('lists prohibited tools first, then paused results, then ambiguous ones; never decided ones', () => {
    const needs = toolsNeedingYou([
      tool('Ambiguous', ambiguousResult()),
      tool('Decided', decidedHighRisk()),
      tool('Paused', WORKED_EXAMPLE),
      tool('Banned', prohibitedResult()),
      tool('Unchecked', null),
    ])
    expect(needs.map((need) => [need.kind, need.tool.name])).toEqual([
      ['prohibited', 'Banned'],
      ['needs-info', 'Paused'],
      ['ambiguous', 'Ambiguous'],
    ])
    expect(needs[1]).toMatchObject({ questions: 1 })
    expect(needs[2]).toMatchObject({ provision: 'art:6:3' })
  })
})

describe('nextDuties', () => {
  it('picks the tool whose duties start soonest, still ahead', () => {
    const later: ClassificationResult = {
      ...decidedHighRisk(),
      obligations: (decidedHighRisk().obligations ?? []).map((duty) =>
        duty.high_risk_route ? { ...duty, applies_from: '2028-08-02' } : duty,
      ),
    }
    const next = nextDuties(
      [tool('Later', later), tool('Sooner', decidedHighRisk()), tool('Limited', limitedRisk())],
      TODAY,
    )
    expect(next).toMatchObject({ date: '2027-12-02', isInForce: false, isAssumed: false })
    expect(next?.tool.name).toBe('Sooner')
  })

  it('skips Art. 50 duties already in force, Art. 111(2) markings and prohibited tools', () => {
    const tools = [
      tool('Limited', limitedRisk()),
      tool('Legacy', legacyMarkedDeployer()),
      tool('Banned', prohibitedResult()),
    ]
    expect(nextDuties(tools, TODAY)).toBeNull()
  })

  it('counts an Art. 50 duty as next while its date is still ahead', () => {
    const next = nextDuties([tool('Limited', limitedRisk())], new Date(2026, 7, 1))
    expect(next).toMatchObject({ date: '2026-08-02', isInForce: false })
  })

  describe('under the original text, with the route date of 2 August 2026', () => {
    const tools = [tool('Screening', decidedHighRisk())]

    it('names it as still ahead the day before', () => {
      expect(nextDuties(tools, new Date(2026, 7, 1), 'original')).toMatchObject({
        date: '2026-08-02',
        isInForce: false,
      })
    })

    it('says the duties apply from that day on', () => {
      expect(nextDuties(tools, new Date(2026, 7, 2), 'original')).toMatchObject({
        date: '2026-08-02',
        isInForce: true,
      })
      expect(nextDuties(tools, TODAY, 'original')).toMatchObject({ isInForce: true })
    })

    it('still names a date ahead before one that has come', () => {
      const limitedAhead = tool('Limited', {
        ...limitedRisk(),
        obligations: (limitedRisk().obligations ?? []).map((duty) => ({
          ...duty,
          applies_from: '2027-01-01',
        })),
      })
      const next = nextDuties([...tools, limitedAhead], TODAY, 'original')
      expect(next).toMatchObject({ date: '2027-01-01', isInForce: false })
      expect(next?.tool.name).toBe('Limited')
    })
  })

  it('names a decided result before an assumed one with an earlier date', () => {
    const later: ClassificationResult = {
      ...decidedHighRisk(),
      obligations: (decidedHighRisk().obligations ?? []).map((duty) =>
        duty.high_risk_route ? { ...duty, applies_from: '2028-08-02' } : duty,
      ),
    }
    const next = nextDuties([tool('Paused', WORKED_EXAMPLE), tool('Decided', later)], TODAY)
    expect(next?.tool.name).toBe('Decided')
    expect(next).toMatchObject({ date: '2028-08-02', isAssumed: false })
  })

  it('names an assumed result, flagged, only when no decided one has dated duties', () => {
    const next = nextDuties([tool('Paused', WORKED_EXAMPLE), tool('Minimal', minimalRisk())], TODAY)
    expect(next?.tool.name).toBe('Paused')
    expect(next).toMatchObject({ date: '2027-12-02', isAssumed: true })
  })
})

describe('transparencyInForce', () => {
  const tools = [
    tool('Video', limitedRisk()),
    tool('Chatbot', limitedRiskProvider()),
    tool('Minimal', minimalRisk()),
  ]

  it('counts the tools whose Art. 50 duties apply from their first day', () => {
    expect(transparencyInForce(tools, new Date(2026, 7, 2))).toEqual({
      tools: 2,
      since: '2026-08-02',
    })
  })

  it('shows nothing the day before', () => {
    expect(transparencyInForce(tools, new Date(2026, 7, 1))).toBeNull()
  })
})

describe('sharedLawDate', () => {
  it('names the consolidation every result was checked against', () => {
    expect(sharedLawDate([tool('A', decidedHighRisk()), tool('B', limitedRisk())])).toBe(
      '2026-07-27',
    )
  })

  it.each<[string, InventoryTool[]]>([
    ['no tools', []],
    ['a tool without a result', [tool('A', decidedHighRisk()), tool('B', null)]],
    [
      'two consolidations',
      [
        tool('A', decidedHighRisk()),
        tool('B', {
          ...limitedRisk(),
          law_text: { document_id: 'x', celex: 'y', version_date: '2026-01-01' },
        }),
      ],
    ],
    [
      'a result on the original text',
      [tool('A', { ...decidedHighRisk(), law_version: 'original' })],
    ],
  ])('names none with %s', (_, tools) => {
    expect(sharedLawDate(tools)).toBeNull()
  })
})
