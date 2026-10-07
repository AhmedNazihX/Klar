import { describe, expect, it } from 'vitest'

import type { ClassificationRun } from '@/features/classify/classification-store'
import { WORKED_EXAMPLE } from '@/test/classify-fixtures'
import { DEPLOYER_DRAFTS, PROVIDER_DRAFTS, PROVIDER_RESULT } from '@/test/documents-fixtures'

import { selectDocument, type ToolDocuments } from './document-selection'

const APPLICANTS: ClassificationRun = {
  toolId: 'a',
  name: 'Applicants',
  description: 'x',
  result: WORKED_EXAMPLE,
}
const DRIVERS: ClassificationRun = {
  toolId: 'd',
  name: 'Drivers',
  description: 'y',
  result: PROVIDER_RESULT,
}
const ENTRIES: ToolDocuments[] = [
  { tool: APPLICANTS, drafts: DEPLOYER_DRAFTS.en },
  { tool: DRIVERS, drafts: PROVIDER_DRAFTS.en },
]

function picked(documentId?: string, toolId?: string): [string, string] | null {
  const selected = selectDocument(ENTRIES, documentId, toolId)
  return selected ? [selected.tool.toolId, selected.draft.document.template] : null
}

describe('Which document is on show', () => {
  it("opens the first tool's first document by default", () => {
    expect(picked()).toEqual(['a', 'art_26_2_oversight'])
  })

  it("opens a tool's first document, or the first tool that has a template", () => {
    expect(picked(undefined, 'd')).toEqual(['d', 'annex_iv_technical_documentation'])
    expect(picked('art_9_risk_management')).toEqual(['d', 'art_9_risk_management'])
  })

  it('shows nothing for a template the tool does not have, or while drafts load', () => {
    expect(picked('art_9_risk_management', 'a')).toBeNull()
    expect(picked('unknown')).toBeNull()
    expect(selectDocument([{ tool: APPLICANTS, drafts: undefined }], undefined, undefined)).toBe(
      null,
    )
  })
})
