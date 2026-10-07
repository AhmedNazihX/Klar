// The inventory table's layout in a real browser (components.md › InventoryTable): at 1280 px all
// six columns fit inside the panel, in German too, with the longest pills and date cells; the
// Class and Status pills stay on one line, the Tool column gives way, and each Basis citation
// stays whole on its line.
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

function tool(
  name: string,
  result: ClassificationResult | null,
  hasUnreadableResult = false,
): InventoryTool {
  return {
    toolId: toolId(),
    name,
    description: `${name} reads every incoming application, scores it against the role and shows HR a ranked shortlist every morning.`,
    createdAt: '2026-10-01T09:00:00+00:00',
    result,
    hasUnreadableResult,
  }
}

/** One tool for each widest cell: the assumed class with "Needs more information", the
 *  ambiguous one with two citations, out of scope, both Art. 111(2) dates, a result that can't
 *  be read ("Gespeichertes Ergebnis nicht lesbar") and a long name. */
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
    tool('Edited file', null, true),
  ]
}

/** How many lines a cell's text runs to: the distinct heights its text boxes sit at. */
function textLines(cell: Element): number {
  const tops = new Set<number>()
  const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const range = document.createRange()
    range.selectNodeContents(node)
    for (const rect of range.getClientRects()) tops.add(Math.round(rect.top))
  }
  return tops.size
}

const CLASS_COLUMN = 2
const STATUS_COLUMN = 5
/** The one pill too wide for a one-line Class column at 1280 px (components.md exception). */
const OUT_OF_SCOPE_DE = 'Außerhalb des Anwendungsbereichs'

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

  it.each([
    ['en', ['High-risk, assumed', 'Needs more information', 'Out of scope']],
    ['de', ['Hochrisiko, angenommen', 'Weitere Angaben nötig']],
  ] as const)('keeps every Class and Status pill on one line (%s)', async (language, widest) => {
    await page.viewport(DESKTOP.width, DESKTOP.height)
    const table = await openInventory(language)
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(widestTools().length)
    const pills = rows.flatMap((row) => {
      const cells = within(row).getAllByRole('cell')
      return [cells[CLASS_COLUMN], cells[STATUS_COLUMN]].flatMap((cell) => [
        ...(cell?.querySelectorAll('[data-kind], [data-status]') ?? []),
      ])
    })
    const oneLine = pills.filter((pill) => pill.textContent !== OUT_OF_SCOPE_DE)
    // Every row's class pill but the two without a result, and the two open statuses.
    expect(pills).toHaveLength(widestTools().length - 2 + 2)
    for (const pill of oneLine) expect(textLines(pill), pill.textContent).toBe(1)
    // The widest one-line pills are among them.
    const texts = oneLine.map((pill) => pill.textContent)
    for (const text of widest) expect(texts).toContain(text)
  })

  it('wraps only the German out-of-scope pill, inside the pill (components.md exception)', async () => {
    await page.viewport(DESKTOP.width, DESKTOP.height)
    const table = await openInventory('de')
    const pill = within(table).getByText(OUT_OF_SCOPE_DE)
    expect(textLines(pill)).toBe(2)
    // Its two lines stay inside the pill and its cell.
    const cell = pill.closest('td')
    if (!cell) throw new Error('The pill sits in its cell.')
    expect(pill.scrollWidth).toBeLessThanOrEqual(pill.clientWidth)
    expect(pill.getBoundingClientRect().right).toBeLessThanOrEqual(
      cell.getBoundingClientRect().right,
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
