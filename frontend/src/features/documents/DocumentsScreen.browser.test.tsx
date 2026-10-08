// The Documents screen's layout in a real browser, on a phone (375 px) and in German: no page
// scrolls sideways, even with a long German title beside the ENTWURF stamp (a skeleton's
// "Qualitätsmanagementsystem (Art. 17)", the Art. 50(3) disclosure), and the document and its
// interview come before the list of documents, so a phone doesn't open on the list.
import type { QueryClient } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import type { CheckedDraft, ClassificationResult, ListedDocument } from '@/api'
import {
  documentDraftsKey,
  documentListKey,
  interviewAnswersKey,
} from '@/features/documents/query-keys'
import { inventoryToolsKey } from '@/hooks/use-inventory-tools'
import type { InventoryTool } from '@/lib/inventory'
import {
  LIMITED_DOCUMENTS,
  LIMITED_RESULT,
  PROVIDER_DOCUMENTS,
  PROVIDER_RESULT,
} from '@/test/documents-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

const PHONE = { width: 375, height: 812 } as const
const DESKTOP = { width: 1440, height: 1000 } as const
const DRIVERS = '0b6f7c1e-2222-4a5b-9c3d-000000000002'
const MOODS = '0b6f7c1e-3333-4a5b-9c3d-000000000003'

type Page = {
  toolId: string
  name: string
  result: ClassificationResult
  documents: readonly ListedDocument[]
  template: string
  draft: CheckedDraft
}

function found<T>(value: T | undefined, what: string): T {
  if (value === undefined) throw new Error(`no ${what} in the fixture`)
  return value
}

/** The Art. 17 skeleton in German. The provider fixture is drafted in English, so its draft
 *  takes the German title the drafter gives it. */
function qualityManagement(): Page {
  const template = 'art_17_quality_management'
  const documents = PROVIDER_DOCUMENTS.list.de.documents
  const listed = found(
    documents.find((item) => item.template === template),
    template,
  )
  const draft = found(PROVIDER_DOCUMENTS.en[template], template)
  return {
    toolId: DRIVERS,
    name: 'Fahrerbewertung',
    result: PROVIDER_RESULT,
    documents,
    template,
    draft: { ...draft, document: { ...draft.document, title: listed.title, language: 'de' } },
  }
}

function emotionDisclosure(): Page {
  const template = 'art_50_3_disclosure'
  return {
    toolId: MOODS,
    name: 'Stimmungsmesser',
    result: LIMITED_RESULT,
    documents: LIMITED_DOCUMENTS.list.de.documents,
    template,
    draft: found(LIMITED_DOCUMENTS.de?.[template], template),
  }
}

/** A query client holding the page's tool, list and draft in `language` (Supabase and the API
 *  aren't reachable here; the tool has no answers yet, and there is no company profile). */
function seededClient(shown: Page, language: 'en' | 'de'): QueryClient {
  const client = createTestQueryClient()
  const tool: InventoryTool = {
    toolId: shown.toolId,
    name: shown.name,
    description: 'A tool whose documents Klar drafts.',
    createdAt: '2026-10-01T09:00:00+00:00',
    result: shown.result,
    hasUnreadableResult: false,
  }
  client.setQueryData(inventoryToolsKey, [tool])
  client.setQueryData(interviewAnswersKey(shown.toolId), {})
  client.setQueryData([...documentListKey(shown.toolId), language], shown.documents)
  client.setQueryData(
    [...documentDraftsKey(shown.toolId), shown.template, language, null],
    shown.draft,
  )
  return client
}

/** Opens the page in German at phone width. */
async function openOnPhone(shown: Page): Promise<HTMLElement> {
  await page.viewport(PHONE.width, PHONE.height)
  await i18n.changeLanguage('de')
  renderRoute(`/app/documents/${shown.template}?tool=${shown.toolId}`, seededClient(shown, 'de'))
  const article = await screen.findByRole(
    'article',
    { name: 'Dokumentvorschau' },
    { timeout: FIRST_RENDER_MS },
  )
  await document.fonts.ready
  return article
}

const PAGES = [
  ['the Art. 17 skeleton', qualityManagement],
  ['the Art. 50(3) disclosure', emotionDisclosure],
] as const

describe('the Documents screen on a phone, in German', () => {
  it.each(PAGES)('never scrolls sideways (%s)', async (_, shown) => {
    await openOnPhone(shown())
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(window.innerWidth)
  })

  it.each(PAGES)(
    'shows the document and its interview before the documents list (%s)',
    async (_, shown) => {
      const article = await openOnPhone(shown())
      const interview = screen.getByRole('region', { name: /Interview/ })
      const list = screen.getByRole('navigation', { name: 'Dokumente' })
      const listTop = list.getBoundingClientRect().top
      expect(article.getBoundingClientRect().top).toBeLessThan(listTop)
      expect(interview.getBoundingClientRect().top).toBeLessThan(listTop)
    },
  )
})

describe('a skeleton on a desktop (DocSkeleton)', () => {
  it('has its numbered sections on the left of the document, and the documents list after', async () => {
    await page.viewport(DESKTOP.width, DESKTOP.height)
    const template = 'annex_iv_technical_documentation'
    const client = seededClient(
      {
        toolId: DRIVERS,
        name: 'Driver scoring',
        result: PROVIDER_RESULT,
        documents: PROVIDER_DOCUMENTS.list.en.documents,
        template,
        draft: found(PROVIDER_DOCUMENTS.en[template], template),
      },
      'en',
    )
    renderRoute(`/app/documents/${template}?tool=${DRIVERS}`, client)
    const article = await screen.findByRole(
      'article',
      { name: 'Document preview' },
      { timeout: FIRST_RENDER_MS },
    )
    const sections = screen.getByRole('navigation', { name: 'Annex IV sections' })
    const documents = screen.getByRole('navigation', { name: 'Documents' })
    expect(sections.getBoundingClientRect().right).toBeLessThanOrEqual(
      article.getBoundingClientRect().left,
    )
    expect(documents.getBoundingClientRect().top).toBeGreaterThanOrEqual(
      article.getBoundingClientRect().bottom,
    )
  })
})
