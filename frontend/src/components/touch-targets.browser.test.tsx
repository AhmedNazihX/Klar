// Every touch target at least 44 px on a 390 px phone (WCAG 2.5.5), on the app screens beyond the
// result (P26 measured the result, ResultScreen.phone.browser.test.tsx; P31 the rest): the
// Inventory, Obligations (both groupings, every duty list opened), Documents (a short document
// and a skeleton, with the list opened), Your data, the opened menu, and Classify with a tool's
// draft (P6's "Adds a new check to <name>" line, checked live in German), in English and German,
// in a real browser.
import type { QueryClient } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page, userEvent } from 'vitest/browser'

import type { ClassificationResult } from '@/api'
import {
  documentDraftsKey,
  documentListKey,
  interviewAnswersKey,
} from '@/features/documents/query-keys'
import { inventoryToolsKey } from '@/hooks/use-inventory-tools'
import type { InventoryTool } from '@/lib/inventory'
import {
  decidedHighRisk,
  legacyMarkedDeployer,
  limitedRisk,
  minimalRisk,
  WORKED_EXAMPLE,
} from '@/test/classify-fixtures'
import {
  LIMITED_DOCUMENTS,
  LIMITED_RESULT,
  PROVIDER_DOCUMENTS,
  PROVIDER_RESULT,
} from '@/test/documents-fixtures'
import { ambiguousResult, prohibitedResult, toolId } from '@/test/inventory-fixtures'
import { clearDraft, saveDraft } from '@/features/classify/classification-store'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { smallTouchTargets } from '@/test/touch-targets'

type Language = 'en' | 'de'

const PHONE = { width: 390, height: 844 } as const
const LANGUAGES = ['en', 'de'] as const
const PROVIDER_TOOL = '0b6f7c1e-2222-4a5b-9c3d-000000000002'
const LIMITED_TOOL = '0b6f7c1e-3333-4a5b-9c3d-000000000003'

function tool(name: string, result: ClassificationResult | null, id = toolId()): InventoryTool {
  return {
    toolId: id,
    name,
    description: `${name}: what it does.`,
    createdAt: '2026-10-01T09:00:00+00:00',
    result,
    hasUnreadableResult: false,
    runNo: result ? 1 : null,
  }
}

/** A tool of every kind the Inventory and Obligations screens lay out differently. */
function everyKindOfTool(): InventoryTool[] {
  return [
    tool('Applicant screening', decidedHighRisk()),
    tool('Call mood scoring', prohibitedResult()),
    tool('Shift planner', WORKED_EXAMPLE),
    tool('CV data extraction', ambiguousResult()),
    tool('Old screener', legacyMarkedDeployer()),
    tool('Product photo generator', limitedRisk()),
    tool('Spam filter', minimalRisk()),
    tool('Draft tool', null),
  ]
}

/** Every running animation that ends has finished (the load motion scales the panels in), so the
 *  boxes measured are the settled ones. */
async function motionSettled(): Promise<void> {
  const ending = document
    .getAnimations()
    .filter((animation) => animation.effect?.getComputedTiming().endTime !== Infinity)
  await Promise.all(ending.map((animation) => animation.finished.catch(() => null)))
}

/** Opens `path` at 390 px in `language`, its data in the cache (Supabase and the API aren't
 *  reachable here). */
async function open(path: string, language: Language, client: QueryClient): Promise<void> {
  await page.viewport(PHONE.width, PHONE.height)
  await i18n.changeLanguage(language)
  renderRoute(path, client)
  await screen.findByRole('heading', { level: 1 })
  await document.fonts.ready
  await motionSettled()
}

function withTools(tools: InventoryTool[]): QueryClient {
  const client = createTestQueryClient()
  client.setQueryData(inventoryToolsKey, tools)
  return client
}

/** The phone's Menu button, which opens the sidebar over the screen. */
const MENU = /^(Menu|Menü)$/

/** Opens every closed list on the screen ("Show all", the Documents toggle), so their controls
 *  are measured too; the menu stays closed, as it would cover them (its own test opens it). */
async function openEveryList(): Promise<void> {
  const closed = screen
    .queryAllByRole('button', { expanded: false })
    .filter(
      (button) =>
        button.getClientRects().length > 0 &&
        !MENU.test(button.getAttribute('aria-label') ?? button.textContent),
    )
  for (const button of closed) await userEvent.click(button)
  await motionSettled()
}

describe('touch targets at 390 px', () => {
  it.each(LANGUAGES)('Inventory (%s)', async (language) => {
    await open('/app/inventory', language, withTools(everyKindOfTool()))
    expect(smallTouchTargets().join('\n')).toBe('')
  })

  it.each(
    LANGUAGES.flatMap((language) => [[language, 'date'] as const, [language, 'tool'] as const]),
  )('Obligations (%s, by %s)', async (language, group) => {
    const path = `/app/obligations${group === 'tool' ? '?group=tool' : ''}`
    await open(path, language, withTools(everyKindOfTool()))
    await openEveryList()
    expect(smallTouchTargets().join('\n')).toBe('')
  })

  it.each(
    LANGUAGES.flatMap((language) => [
      [language, 'art_50_3_disclosure'] as const,
      [language, 'art_17_quality_management'] as const,
    ]),
  )('Documents (%s, %s)', async (language, template) => {
    const isSkeleton = template === 'art_17_quality_management'
    const shown = isSkeleton
      ? tool('Driver scoring', PROVIDER_RESULT, PROVIDER_TOOL)
      : tool('Mood meter', LIMITED_RESULT, LIMITED_TOOL)
    const documents = isSkeleton ? PROVIDER_DOCUMENTS : LIMITED_DOCUMENTS
    const draft = documents.en[template]
    if (!draft) throw new Error(`no ${template} draft in the fixture`)
    const client = withTools([shown])
    client.setQueryData(interviewAnswersKey(shown.toolId), {})
    client.setQueryData(
      [...documentListKey(shown.toolId), language],
      documents.list[language].documents,
    )
    client.setQueryData([...documentDraftsKey(shown.toolId), template, language, null], draft)
    await open(`/app/documents/${template}?tool=${shown.toolId}`, language, client)
    await screen.findByRole('article')
    await openEveryList()
    expect(smallTouchTargets().join('\n')).toBe('')
  })

  it.each(LANGUAGES)('Your data (%s)', async (language) => {
    await open('/app/your-data', language, createTestQueryClient())
    expect(smallTouchTargets().join('\n')).toBe('')
  })

  it.each(LANGUAGES)('the opened menu (%s)', async (language) => {
    await open('/app/inventory', language, withTools(everyKindOfTool()))
    await userEvent.click(screen.getByRole('button', { name: MENU }))
    const menu = await screen.findByRole('navigation', {
      name: language === 'en' ? 'App' : 'App-Navigation',
    })
    const sidebar = menu.parentElement
    if (!sidebar) throw new Error('The navigation sits in the sidebar.')
    expect(smallTouchTargets(sidebar).join('\n')).toBe('')
  })

  it.each([
    ['en', 'Adds a new check to Bewerbungsranking und Vorauswahl.'],
    ['de', 'Fügt eine neue Prüfung für Bewerbungsranking und Vorauswahl hinzu.'],
  ] as const)('Classify, a tool’s next check (%s)', async (language, note) => {
    const name = 'Bewerbungsranking und Vorauswahl'
    saveDraft({ name, description: 'Ranks applicants.' }, { toolId: toolId(), name })
    try {
      await open('/app/classify', language, createTestQueryClient())
      const line = screen.getByText(note)
      expect(line).toBeVisible()
      // The line wraps inside the page, never sideways.
      expect(line.scrollWidth).toBeLessThanOrEqual(line.clientWidth)
      expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(window.innerWidth)
      expect(smallTouchTargets().join('\n')).toBe('')
    } finally {
      clearDraft()
    }
  })
})
