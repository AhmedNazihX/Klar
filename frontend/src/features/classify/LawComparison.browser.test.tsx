// "Original Act vs amended" in a real browser: filled with its widest values (the German Annex I
// Section names), its table stays inside its panel, every date and Annex point sits whole on one
// line and nothing scrolls sideways, on a 390 px phone and in the reviewer view's 380 px column on
// the desktop; without an Annex point it keeps its three columns. Under the original text the
// summary's and the deciding question's dates show the original Art. 113 date only (the switch's
// CSS, decision 026 item 11).
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import type { ClassificationResult } from '@/api'
import { originalRunKey } from '@/hooks/use-original-run'
import {
  ANNEX_I_QUESTION,
  annexINeedsInfo,
  decidedHighRisk,
  WORKED_EXAMPLE_DESCRIPTION,
} from '@/test/classify-fixtures'
import {
  PRESS_GUARD_DESCRIPTION,
  pressGuardAmended,
  pressGuardOriginal,
} from '@/test/original-text-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { putRun, type ClassificationRun } from './classification-store'

const PHONE = { width: 390, height: 844 } as const
const DESKTOP = { width: 1440, height: 1000 } as const
const TOOL_ID = 'press-guard'
const PANEL_NAME = { en: 'Original Act vs amended', de: 'Ursprüngliche und geänderte Fassung' }
const BASIS = { en: 'Annex I Section B point 21', de: 'Anhang I Abschnitt B Nr. 21' }

async function openComparison(
  language: 'en' | 'de',
  amended: ClassificationResult = pressGuardAmended(),
  original: ClassificationResult | null = pressGuardOriginal(),
): Promise<HTMLElement> {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  const run: ClassificationRun = {
    toolId: TOOL_ID,
    name: 'Press guard',
    description: PRESS_GUARD_DESCRIPTION,
    result: amended,
  }
  putRun(client, run)
  if (original) client.setQueryData(originalRunKey(run), original)
  renderRoute(`/app/inventory/${TOOL_ID}?view=reviewer`, client)
  const panel = await screen.findByRole('region', { name: PANEL_NAME[language] })
  await document.fonts.ready
  return panel
}

function sidewaysOverflow(): number {
  const root = document.documentElement
  return root.scrollWidth - root.clientWidth
}

/** How many lines a cell's value takes (not the column name a stacked row shows beside it): its
 *  text's line boxes, counted by their distinct tops. */
function lineCount(cell: Element): number {
  const value = cell.lastElementChild
  if (!value) throw new Error('A cell holds its value.')
  const range = document.createRange()
  range.selectNodeContents(value)
  const tops = new Set(Array.from(range.getClientRects(), (rect) => Math.round(rect.top)))
  return tops.size
}

describe('Original Act vs amended, filled', () => {
  it.each([
    ['en', PHONE],
    ['de', PHONE],
    ['en', DESKTOP],
    ['de', DESKTOP],
  ] as const)('fits its panel, each value on one line (%s, %o)', async (language, viewport) => {
    await page.viewport(viewport.width, viewport.height)
    const panel = await openComparison(language)
    const table = within(panel).getByRole('table')
    expect(table.getBoundingClientRect().right).toBeLessThanOrEqual(
      panel.getBoundingClientRect().right,
    )
    expect(sidewaysOverflow()).toBe(0)
    // Every value, the Annex points and the dates included, sits whole on one line.
    const cells = within(table).getAllByRole('cell')
    expect(cells.map((cell) => [cell.lastElementChild?.textContent, lineCount(cell)])).toEqual(
      cells.map((cell) => [cell.lastElementChild?.textContent, 1]),
    )
    // The labels keep their words whole too, and the panel shows the press guard's Annex points.
    for (const label of within(table).getAllByRole('rowheader')) {
      expect(label.scrollWidth).toBeLessThanOrEqual(label.clientWidth)
    }
    expect(table).toHaveTextContent(BASIS[language])
  })
})

describe('Original Act vs amended, before the check', () => {
  it.each([
    ['de', PHONE],
    ['de', DESKTOP],
  ] as const)(
    'keeps the three columns, the dates each on one line (%s, %o)',
    async (language, viewport) => {
      await page.viewport(viewport.width, viewport.height)
      const panel = await openComparison(language, decidedHighRisk(), null)
      const table = within(panel).getByRole('table')
      const [original, amended] = within(table).getAllByRole('columnheader')
      if (!original || !amended) throw new Error('The table has two columns.')
      // Side by side, one row: the table didn't stack (it has no Annex point to fit).
      expect(original.getBoundingClientRect().top).toBe(amended.getBoundingClientRect().top)
      expect(original.getBoundingClientRect().right).toBeLessThan(
        amended.getBoundingClientRect().left,
      )
      const dates = within(table).getAllByRole('cell').slice(-2)
      expect(dates.map((cell) => [cell.textContent, lineCount(cell)])).toEqual([
        ['2. Aug. 2026', 1],
        ['2. Dez. 2027', 1],
      ])
      expect(sidewaysOverflow()).toBe(0)
    },
  )
})

describe('the summary under the original text', () => {
  it('shows only the original Art. 113 date for the Annex III route', async () => {
    await page.viewport(DESKTOP.width, DESKTOP.height)
    await i18n.changeLanguage('en')
    const client = createTestQueryClient()
    putRun(client, {
      toolId: 'applicant-screening',
      name: 'Applicant screening',
      description: WORKED_EXAMPLE_DESCRIPTION,
      result: decidedHighRisk(),
    })
    renderRoute('/app/inventory/applicant-screening?law=original', client)
    const summary = await screen.findByRole('region', { name: 'Result' })
    expect(summary.innerText).toContain('2 August 2026')
    expect(summary.innerText).not.toContain('2 December 2027')
  })

  // The deciding question's "if yes" date, on the Annex I route: 2 August 2027 (Art. 113(c))
  // under the original text, where the amended text says 2 August 2028.
  it.each([
    ['en', '2 August 2027', '2 August 2028'],
    ['de', '2. August 2027', '2. August 2028'],
  ] as const)(
    "shows the deciding question's Annex I date under the original text (%s)",
    async (language, original, amended) => {
      await page.viewport(DESKTOP.width, DESKTOP.height)
      await i18n.changeLanguage(language)
      const client = createTestQueryClient()
      putRun(client, {
        toolId: 'press-guard',
        name: 'Press guard',
        description: PRESS_GUARD_DESCRIPTION,
        result: annexINeedsInfo(),
      })
      renderRoute('/app/inventory/press-guard?law=original', client)
      const question = await screen.findByRole('region', { name: ANNEX_I_QUESTION })
      expect(question.innerText).toContain(original)
      expect(question.innerText).not.toContain(amended)
    },
  )
})
