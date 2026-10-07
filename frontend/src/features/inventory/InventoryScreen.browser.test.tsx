// The inventory table's layout in a real browser (components.md › InventoryTable): at 1280 px all
// six columns fit inside the panel, in German too, with the longest pills and date cells; the
// Tool column gives way, and each Basis citation stays whole on its line.
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import type { ClassificationResult } from '@/api'
import { inventoryToolsKey } from '@/hooks/use-inventory-tools'
import type { InventoryTool } from '@/lib/inventory'
import {
  decidedHighRisk,
  legacyForPublicAuthorities,
  legacyMarkedDeployer,
  outOfScope,
  WORKED_EXAMPLE,
} from '@/test/classify-fixtures'
import { ambiguousResult, prohibitedResult, toolId } from '@/test/inventory-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

const DESKTOP = { width: 1280, height: 900 } as const

function tool(name: string, result: ClassificationResult | null): InventoryTool {
  return {
    toolId: toolId(),
    name,
    description: `${name} reads every incoming application, scores it against the role and shows HR a ranked shortlist every morning.`,
    createdAt: '2026-10-01T09:00:00+00:00',
    result,
    hasUnreadableResult: false,
  }
}

/** One tool for each widest cell: the assumed class with "Needs more information", the
 *  ambiguous one with two citations, out of scope, both Art. 111(2) dates, and a long name. */
function widestTools(): InventoryTool[] {
  return [
    tool('Applicant screening and ranking for every open position', decidedHighRisk()),
    tool('Call mood scoring', prohibitedResult()),
    tool('Shift planner', WORKED_EXAMPLE),
    tool('CV data extraction', ambiguousResult()),
    tool('Old screener', legacyMarkedDeployer()),
    tool('Benefits checker', legacyForPublicAuthorities()),
    tool('Invoice matching', outOfScope()),
    tool('Draft tool', null),
  ]
}

async function openInventory(language: 'en' | 'de'): Promise<HTMLElement> {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  // Supabase isn't configured here, so the screen reads the tools from the cache only.
  client.setQueryData(inventoryToolsKey, widestTools())
  renderRoute('/app/inventory', client)
  const name = language === 'de' ? 'Ihre Tools und ihre Ergebnisse' : 'Your tools and their results'
  const table = await screen.findByRole('table', { name }, { timeout: FIRST_RENDER_MS })
  await document.fonts.ready
  return table
}

describe('the inventory table at 1280 px', () => {
  it.each(['en', 'de'] as const)('fits all six columns inside its panel (%s)', async (language) => {
    await page.viewport(DESKTOP.width, DESKTOP.height)
    const table = await openInventory(language)
    const panel = table.closest('section')
    if (!panel) throw new Error('The table sits in its glass panel.')

    expect(table.scrollWidth).toBeLessThanOrEqual(panel.clientWidth)
    // The last column's right edge is inside the panel: nothing to scroll to.
    const status = within(table).getAllByRole('columnheader').at(-1)
    expect(status?.getBoundingClientRect().right).toBeLessThanOrEqual(
      panel.getBoundingClientRect().right,
    )
  })

  it.each(['en', 'de'] as const)(
    'keeps each Basis citation and Art. 111(2) tag whole (%s)',
    async (language) => {
      await page.viewport(DESKTOP.width, DESKTOP.height)
      const table = await openInventory(language)
      const references = within(table).getAllByText(/^(Art\.|Annex|Anhang)/, { selector: 'span' })
      expect(references.length).toBeGreaterThan(4)
      for (const reference of references) {
        // Its text boxes all sit at the same height: never broken mid-reference.
        const tops = new Set([...reference.getClientRects()].map((rect) => Math.round(rect.top)))
        expect(tops.size, reference.textContent).toBe(1)
      }
    },
  )
})
