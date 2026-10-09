// The duty rows on a phone, in a real browser (canvas note: "A citation never truncates"): at
// 390 px the "Draft ready" link and the citation go under the duty, so the duty keeps at least
// half the row in English and German, with both groupings, and the citation stays whole inside
// the row.
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import type { ClassificationResult } from '@/api'
import { inventoryToolsKey } from '@/hooks/use-inventory-tools'
import type { InventoryTool } from '@/lib/inventory'
import { decidedHighRisk, limitedRisk } from '@/test/classify-fixtures'
import { toolId } from '@/test/inventory-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

const PHONE = { width: 390, height: 844 } as const
/** The share of the row a duty keeps beside its draft link and citation. */
const MIN_LABEL_SHARE = 0.5

function tool(name: string, result: ClassificationResult): InventoryTool {
  return {
    toolId: toolId(),
    name,
    description: `${name}: what it does.`,
    createdAt: '2026-10-01T09:00:00+00:00',
    result,
    hasUnreadableResult: false,
  }
}

/** Applicant screening's drafts (Art. 26(2), (7), (11)) and Art. 50(4)'s, plus one duty with a
 *  draft and a citation longer than any real one ("Art. 5 Abs. 1 Buchst. c Ziff. i"). */
function toolsWithDrafts(): InventoryTool[] {
  const photos = limitedRisk()
  const [literacy] = photos.obligations ?? []
  if (!literacy) throw new Error('The fixture has duties.')
  const longest = {
    ...literacy,
    key: 'longest-citation',
    article: 'art:5:1:c:i',
    document: 'art_50_4_disclosure',
    label_en: 'Disclose AI-made content that could pass as real',
    label_de: 'Offenlegen, wenn Inhalte echt wirken, aber KI-erzeugt sind',
  }
  return [
    tool('Applicant screening', decidedHighRisk()),
    tool('Product photo generator', {
      ...photos,
      obligations: [...(photos.obligations ?? []), longest],
    }),
  ]
}

async function openObligations(language: 'en' | 'de', group: 'date' | 'tool'): Promise<void> {
  await page.viewport(PHONE.width, PHONE.height)
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  // Supabase isn't configured here, so the screen reads the tools from the cache only.
  client.setQueryData(inventoryToolsKey, toolsWithDrafts())
  renderRoute(`/app/obligations${group === 'tool' ? '?group=tool' : ''}`, client)
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
  await document.fonts.ready
  for (const button of screen.queryAllByRole('button', { name: /^(Show all|Alle \d+)/ })) {
    button.click()
  }
}

describe('the duty rows at 390 px', () => {
  it.each([
    ['en', 'date', 'Draft ready'],
    ['en', 'tool', 'Draft ready'],
    ['de', 'date', 'Entwurf bereit'],
    ['de', 'tool', 'Entwurf bereit'],
  ] as const)(
    'keep each duty readable beside "Draft ready" and its citation (%s, by %s)',
    async (language, group, draftReady) => {
      await openObligations(language, group)
      const links = await screen.findAllByRole('link', { name: draftReady })
      // Three Art. 26 drafts, Art. 50(4)'s and the longest citation's.
      expect(links).toHaveLength(5)
      for (const link of links) {
        const row = link.closest('li')
        if (!row) throw new Error('A draft link sits in its duty row.')
        const box = within(row).getByRole('checkbox')
        const label = within(row).getByText(box.getAttribute('aria-label') ?? '')
        const rowBox = row.getBoundingClientRect()
        const share = label.getBoundingClientRect().width / rowBox.width
        expect(share, label.textContent).toBeGreaterThanOrEqual(MIN_LABEL_SHARE)
        // The citation stays whole and inside the row.
        const citation = row.lastElementChild?.lastElementChild?.lastElementChild
        if (!(citation instanceof HTMLElement)) throw new Error('The row ends in its citation.')
        expect(citation.scrollWidth).toBeLessThanOrEqual(citation.clientWidth)
        expect(citation.getBoundingClientRect().right).toBeLessThanOrEqual(rowBox.right + 0.5)
      }
    },
  )
})
