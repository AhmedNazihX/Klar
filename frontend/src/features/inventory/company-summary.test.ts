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
    expect(next?.tool.name).toBe('Sooner')
    expect(next?.appliesFrom).toEqual({
      kind: 'route',
      amended: '2027-12-02',
      original: '2026-08-02',
    })
  })

  it('skips duties already in force, Art. 111(2) markings and prohibited tools', () => {
    const tools = [
      tool('Limited', limitedRisk()),
      tool('Legacy', legacyMarkedDeployer()),
      tool('Banned', prohibitedResult()),
    ]
    expect(nextDuties(tools, TODAY)).toBeNull()
  })

  it('counts an Art. 50 duty as next while its date is still ahead', () => {
    const next = nextDuties([tool('Limited', limitedRisk())], new Date(2026, 7, 1))
    expect(next?.appliesFrom).toEqual({ kind: 'from', date: '2026-08-02' })
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
