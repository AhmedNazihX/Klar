// The result's layout in a real browser: with a full result on screen, nothing scrolls sideways
// on a 390 px phone, and a step row's citations are never broken mid-reference on the desktop,
// in German too (localisation.md).
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import type { ClassificationResult } from '@/api'
import {
  annexIIINeedsInfo,
  decidedHighRisk,
  WORKED_EXAMPLE_DESCRIPTION,
} from '@/test/classify-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { putRun, type ClassificationRun } from './classification-store'

const PHONE = { width: 390, height: 844 } as const
const DESKTOP = { width: 1440, height: 1000 } as const
const TOOL_ID = 'applicant-screening'

async function openResult(
  language: 'en' | 'de',
  view?: 'reviewer',
  result: ClassificationResult = decidedHighRisk(),
): Promise<void> {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  const run: ClassificationRun = {
    toolId: TOOL_ID,
    name: 'Applicant screening',
    description: WORKED_EXAMPLE_DESCRIPTION,
    result,
  }
  putRun(client, run)
  renderRoute(`/app/inventory/${TOOL_ID}${view ? '?view=reviewer' : ''}`, client)
  await screen.findByRole('heading', { level: 1, name: 'Applicant screening' })
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

describe('a paused result with more questions at 390 px', () => {
  /** The deciding question and another one, so the run action is the plural, longest label. */
  function pausedWithQuestions(): ClassificationResult {
    const base = annexIIINeedsInfo()
    const more = {
      id: 'human_review',
      text: 'Does a person review the shortlist before it affects hiring decisions?',
      options: ['yes', 'no', 'not_sure'] as const,
    }
    return {
      ...base,
      follow_up_questions: [
        ...(base.follow_up_questions ?? []),
        { ...more, options: [...more.options] },
      ],
    }
  }

  it.each([
    ['en', 'Add answers and run again'],
    ['de', 'Antworten hinzufügen und erneut prüfen'],
  ] as const)(
    'wraps the run action instead of scrolling sideways (%s)',
    async (language, label) => {
      await page.viewport(PHONE.width, PHONE.height)
      await openResult(language, undefined, pausedWithQuestions())
      const button = screen.getByRole('button', { name: label })
      // It stays inside its panel's padding: before the fix, the German label stuck out 5 px.
      const panel = button.parentElement as HTMLElement
      const inner =
        panel.getBoundingClientRect().right - parseFloat(getComputedStyle(panel).paddingRight)
      expect(button.getBoundingClientRect().right, label).toBeLessThanOrEqual(inner)
      expect(sidewaysOverflow()).toBe(0)
    },
  )
})

describe('the duty rows at 1280 px', () => {
  it.each(['en', 'de'] as const)(
    'keep the label and its citation on one line (%s)',
    async (language) => {
      await page.viewport(1280, DESKTOP.height)
      await openResult(language)
      const heading = language === 'en' ? 'What you need to do' : 'Was Sie tun müssen'
      const section = screen.getByRole('region', { name: heading })
      const rows = within(section).getAllByRole('listitem')
      let checked = 0
      for (const row of rows) {
        const reference = within(row).queryByText(/^(Art\.|Annex|Anhang)/)
        if (!reference) continue
        const column = within(row).getByRole('checkbox').closest('label')?.nextElementSibling
        const columnBottom = column?.getBoundingClientRect().bottom ?? 0
        // The citation starts above the text block's bottom edge: beside it, not stacked under it.
        expect(reference.getBoundingClientRect().top, row.textContent).toBeLessThan(columnBottom)
        checked += 1
      }
      expect(checked).toBeGreaterThan(0)
    },
  )
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
