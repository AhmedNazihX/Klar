// The result's layout in a real browser: with a full result on screen, nothing scrolls sideways
// on a 390 px phone, and a step row's citations are never broken mid-reference on the desktop,
// in German too (localisation.md).
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import { decidedHighRisk, WORKED_EXAMPLE_DESCRIPTION } from '@/test/classify-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

import { classificationRunOptions, type ClassificationRun } from './classification-store'

const PHONE = { width: 390, height: 844 } as const
const DESKTOP = { width: 1440, height: 1000 } as const
const TOOL_ID = 'applicant-screening'

async function openResult(language: 'en' | 'de', view?: 'reviewer'): Promise<void> {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  const run: ClassificationRun = {
    toolId: TOOL_ID,
    name: 'Applicant screening',
    description: WORKED_EXAMPLE_DESCRIPTION,
    result: decidedHighRisk(),
  }
  client.setQueryData(classificationRunOptions(TOOL_ID).queryKey, run)
  renderRoute(`/app/inventory/${TOOL_ID}${view ? '?view=reviewer' : ''}`, client)
  await screen.findByRole(
    'heading',
    { level: 1, name: 'Applicant screening' },
    { timeout: FIRST_RENDER_MS },
  )
  await document.fonts.ready
}

/** How far the page reaches past the window's right edge, in px (0 when nothing sticks out). */
function sidewaysOverflow(): number {
  const root = document.documentElement
  return root.scrollWidth - root.clientWidth
}

describe('the result at 390 px', () => {
  it.each([
    ['en', undefined],
    ['de', undefined],
    ['en', 'reviewer'],
    ['de', 'reviewer'],
  ] as const)('(%s, %s view) does not scroll sideways', async (language, view) => {
    await page.viewport(PHONE.width, PHONE.height)
    await openResult(language, view)
    expect(sidewaysOverflow()).toBe(0)
  })
})

describe('the step rows on a desktop', () => {
  it.each(['en', 'de'] as const)('keep every citation on one line (%s)', async (language) => {
    await page.viewport(DESKTOP.width, DESKTOP.height)
    await openResult(language)
    const heading = language === 'en' ? 'How Klar got here' : 'Wie Klar zum Ergebnis kam'
    const section = screen.getByRole('region', { name: heading })
    const references = within(section).getAllByText(/^(Art\.|Annex|Anhang)/)
    expect(references.length).toBeGreaterThan(0)
    for (const reference of references) {
      // Its text boxes all sit at the same height: never broken mid-reference.
      const tops = new Set([...reference.getClientRects()].map((rect) => Math.round(rect.top)))
      expect(tops.size, reference.textContent).toBe(1)
    }
    expect(sidewaysOverflow()).toBe(0)
  })
})
