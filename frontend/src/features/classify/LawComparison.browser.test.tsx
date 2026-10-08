// "Original Act vs amended" in a real browser: filled with its widest values (the German Annex I
// Section names), its table stays inside its panel and nothing scrolls sideways, on a 390 px
// phone and in the reviewer view's 380 px column on the desktop. Under the original text the
// summary's date shows the original Art. 113 date only (the switch's CSS, decision 026 item 11).
import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import { originalRunKey } from '@/hooks/use-original-run'
import { decidedHighRisk, WORKED_EXAMPLE_DESCRIPTION } from '@/test/classify-fixtures'
import {
  PRESS_GUARD_DESCRIPTION,
  pressGuardAmended,
  pressGuardOriginal,
} from '@/test/original-text-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

import { putRun, type ClassificationRun } from './classification-store'

const PHONE = { width: 390, height: 844 } as const
const DESKTOP = { width: 1440, height: 1000 } as const
const TOOL_ID = 'press-guard'
const PANEL_NAME = { en: 'Original Act vs amended', de: 'Ursprüngliche und geänderte Fassung' }

async function openComparison(language: 'en' | 'de'): Promise<HTMLElement> {
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  const run: ClassificationRun = {
    toolId: TOOL_ID,
    name: 'Press guard',
    description: PRESS_GUARD_DESCRIPTION,
    result: pressGuardAmended(),
  }
  putRun(client, run)
  client.setQueryData(originalRunKey(run), pressGuardOriginal())
  renderRoute(`/app/inventory/${TOOL_ID}?view=reviewer`, client)
  const panel = await screen.findByRole(
    'region',
    { name: PANEL_NAME[language] },
    { timeout: FIRST_RENDER_MS },
  )
  await document.fonts.ready
  return panel
}

function sidewaysOverflow(): number {
  const root = document.documentElement
  return root.scrollWidth - root.clientWidth
}

describe('Original Act vs amended, filled', () => {
  it.each([
    ['en', PHONE],
    ['de', PHONE],
    ['en', DESKTOP],
    ['de', DESKTOP],
  ] as const)('fits its panel (%s, %o)', async (language, viewport) => {
    await page.viewport(viewport.width, viewport.height)
    const panel = await openComparison(language)
    const table = panel.querySelector('table')
    if (!table) throw new Error('The comparison is a table.')
    expect(table.getBoundingClientRect().right).toBeLessThanOrEqual(
      panel.getBoundingClientRect().right,
    )
    expect(sidewaysOverflow()).toBe(0)
  })
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
    const summary = await screen.findByRole(
      'region',
      { name: 'Result' },
      { timeout: FIRST_RENDER_MS },
    )
    expect(summary.innerText).toContain('2 August 2026')
    expect(summary.innerText).not.toContain('2 December 2027')
  })
})
