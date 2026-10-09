import { describe, expect, it } from 'vitest'

import type { InventoryTool } from '@/lib/inventory'
import { WORKED_EXAMPLE } from '@/test/classify-fixtures'

import { reportTool } from './use-report-export'

function storedTool(result: InventoryTool['result']): InventoryTool {
  return {
    toolId: 'tool-1',
    name: 'CV screener',
    description: 'Ranks applicants',
    createdAt: '2026-09-27T10:00:00Z',
    result,
    hasUnreadableResult: false,
  }
}

describe('reportTool', () => {
  it('sends the role a provider also has, so its deployer duties are matched', () => {
    const both = { ...WORKED_EXAMPLE, role: 'provider', also_role: 'deployer' } as const
    const sent = reportTool(storedTool(both), 'en')
    expect(sent.role).toBe('provider')
    expect(sent.also_role).toBe('deployer')
  })

  it('sends no second role when the result has none', () => {
    expect(reportTool(storedTool({ ...WORKED_EXAMPLE, also_role: null }), 'en').also_role).toBe(
      null,
    )
  })
})
