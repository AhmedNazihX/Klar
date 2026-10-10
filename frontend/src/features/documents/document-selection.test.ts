import { describe, expect, it } from 'vitest'

import type { DocumentTool } from '@/hooks/use-document-drafts'
import type { InventoryTool } from '@/lib/inventory'
import { WORKED_EXAMPLE } from '@/test/classify-fixtures'
import { DEPLOYER_DOCUMENTS, PROVIDER_DOCUMENTS, PROVIDER_RESULT } from '@/test/documents-fixtures'

import { documentTools, selectDocument, type ToolDocuments } from './document-selection'

const APPLICANTS: DocumentTool = { toolId: 'a', name: 'Applicants', result: WORKED_EXAMPLE }
const DRIVERS: DocumentTool = { toolId: 'd', name: 'Drivers', result: PROVIDER_RESULT }
const ENTRIES: ToolDocuments[] = [
  { tool: APPLICANTS, documents: DEPLOYER_DOCUMENTS.list.en.documents },
  { tool: DRIVERS, documents: PROVIDER_DOCUMENTS.list.en.documents },
]

function picked(documentId?: string, toolId?: string): [string, string] | null {
  const selected = selectDocument(ENTRIES, documentId, toolId)
  return selected ? [selected.tool.toolId, selected.document.template] : null
}

describe('Which document is on show', () => {
  it("opens the first tool's first document by default", () => {
    expect(picked()).toEqual(['a', 'art_26_2_oversight'])
  })

  it("opens a tool's first document, or the first tool that has a template", () => {
    expect(picked(undefined, 'd')).toEqual(['d', 'annex_iv_technical_documentation'])
    expect(picked('art_9_risk_management')).toEqual(['d', 'art_9_risk_management'])
  })

  it('shows nothing for a template the tool does not have, or while the list loads', () => {
    expect(picked('art_9_risk_management', 'a')).toBeNull()
    expect(picked('unknown')).toBeNull()
    expect(selectDocument([{ tool: APPLICANTS, documents: undefined }], undefined, undefined)).toBe(
      null,
    )
  })
})

describe('Which tools have documents', () => {
  function tool(toolId: string, result: InventoryTool['result']): InventoryTool {
    return {
      toolId,
      name: null,
      description: 'x',
      createdAt: '2026-10-01T09:00:00+00:00',
      result,
      hasUnreadableResult: false,
      runNo: 1,
    }
  }

  it("keeps the inventory's tools with a result, under their inventory ids", () => {
    const tools = [tool('t1', WORKED_EXAMPLE), tool('t2', null), tool('t3', PROVIDER_RESULT)]
    expect(documentTools(tools)).toEqual([
      { toolId: 't1', name: null, result: WORKED_EXAMPLE },
      { toolId: 't3', name: null, result: PROVIDER_RESULT },
    ])
  })
})
