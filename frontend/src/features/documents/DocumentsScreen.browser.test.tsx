// The Documents screen's layout in a real browser. On a phone (375 px), in German: no page
// scrolls sideways and a long title breaks inside the document, beside the ENTWURF stamp (a
// skeleton's "Qualitätsmanagementsystem (Art. 17)", a disclosure title with a long run of
// digits), and the page
// opens on the document, with the documents list (and a skeleton's section list) closed behind a
// toggle. On a desktop (1440 px): what is on the left comes first in the reading and tab order
// too (WCAG 1.3.2, 2.4.3), the documents list before the document, a skeleton's sections before
// its body.
import type { QueryClient } from '@tanstack/react-query'
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it, vi } from 'vitest'
import { page, userEvent } from 'vitest/browser'

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

type Viewport = { width: number; height: number }
type Language = 'en' | 'de'

const PHONE: Viewport = { width: 375, height: 812 }
const DESKTOP: Viewport = { width: 1440, height: 1000 }
const DRIVERS = '0b6f7c1e-2222-4a5b-9c3d-000000000002'
const MOODS = '0b6f7c1e-3333-4a5b-9c3d-000000000003'
/** A title with a run of digits too wide for a 375 px page at the title's size. Hyphenation
 *  can't break digits (it does break long German words), so only the title's
 *  `overflow-wrap: anywhere` keeps this one inside the document. */
const LONG_TITLE = 'Hinweis zur Kamera 40063813339314006381333931400638133393 (Art. 50 Abs. 3)'
/** More tab stops than the shell and the page have before the document's interview. */
const MAX_TABS = 80

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

/** The Art. 17 skeleton in `language`. The provider fixture is drafted in English, so a German
 *  draft takes the German title the list gives it. */
function qualityManagement(language: Language = 'de'): Page {
  const template = 'art_17_quality_management'
  const documents = PROVIDER_DOCUMENTS.list[language].documents
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
    draft: { ...draft, document: { ...draft.document, title: listed.title, language } },
  }
}

/** The Art. 50(3) disclosure in `language`; in German with `LONG_TITLE`, which only the
 *  title's own line breaking keeps inside a phone's page. */
function emotionDisclosure(language: Language = 'de'): Page {
  const template = 'art_50_3_disclosure'
  const drafts = language === 'de' ? LIMITED_DOCUMENTS.de : LIMITED_DOCUMENTS.en
  const draft = found(drafts?.[template], template)
  return {
    toolId: MOODS,
    name: 'Stimmungsmesser',
    result: LIMITED_RESULT,
    documents: LIMITED_DOCUMENTS.list[language].documents,
    template,
    draft:
      language === 'de' ? { ...draft, document: { ...draft.document, title: LONG_TITLE } } : draft,
  }
}

/** A query client holding the page's tool, list and draft in `language` (Supabase and the API
 *  aren't reachable here; the tool has no answers yet, and there is no company profile). */
function seededClient(shown: Page, language: Language): QueryClient {
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

/** Opens the page at `viewport` in `language`; gives the document's article. */
async function open(shown: Page, viewport: Viewport, language: Language): Promise<HTMLElement> {
  await page.viewport(viewport.width, viewport.height)
  await i18n.changeLanguage(language)
  renderRoute(`/app/documents/${shown.template}?tool=${shown.toolId}`, seededClient(shown, language))
  const article = await screen.findByRole(
    'article',
    { name: language === 'de' ? 'Dokumentvorschau' : 'Document preview' },
    { timeout: FIRST_RENDER_MS },
  )
  await document.fonts.ready
  return article
}

/** Whether `first` comes before `second` in the document, which is the reading and tab order. */
function precedes(first: Element, second: Element): boolean {
  return Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)
}

/** Tabs from the top of the page until focus enters one of `targets`; gives the one it entered. */
async function firstTabbedInto(targets: readonly HTMLElement[]): Promise<HTMLElement | null> {
  for (let tabs = 0; tabs < MAX_TABS; tabs += 1) {
    await userEvent.tab()
    const reached = targets.find((target) => target.contains(document.activeElement))
    if (reached) return reached
  }
  return null
}

const PHONE_PAGES = [
  ['the Art. 17 skeleton', () => qualityManagement()],
  ['the Art. 50(3) disclosure', () => emotionDisclosure()],
] as const

describe('the Documents screen on a phone, in German', () => {
  it.each(PHONE_PAGES)(
    'never scrolls sideways, and the title breaks inside the document (%s)',
    async (_, opened) => {
      const shown = opened()
      const article = await open(shown, PHONE, 'de')
      expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(window.innerWidth)
      const title = within(article).getByRole('heading', { name: shown.draft.document.title })
      expect(title.scrollWidth).toBeLessThanOrEqual(title.clientWidth)
      expect(title.getBoundingClientRect().right).toBeLessThanOrEqual(
        article.getBoundingClientRect().right,
      )
    },
  )

  it.each(PHONE_PAGES)(
    'opens on the document, the documents list closed behind its toggle (%s)',
    async (_, opened) => {
      const shown = opened()
      const article = await open(shown, PHONE, 'de')
      const toggle = screen.getByRole('button', {
        name: `Dokumente (${String(shown.documents.length)})`,
      })
      expect(toggle).toHaveAttribute('aria-expanded', 'false')
      expect(screen.queryByRole('navigation', { name: 'Dokumente' })).toBeNull()
      expect(article.getBoundingClientRect().top).toBeLessThan(PHONE.height)

      await userEvent.click(toggle)
      expect(toggle).toHaveAttribute('aria-expanded', 'true')
      const list = screen.getByRole('navigation', { name: 'Dokumente' })
      const current = within(list).getByRole('link', { current: 'page' })
      await vi.waitFor(() => {
        expect(current).toBeVisible()
      })
    },
  )

  it("closes a skeleton's section list too, and opens it on request", async () => {
    await open(qualityManagement(), PHONE, 'de')
    const toggle = screen.getByRole('button', { name: 'Abschnitte nach Art. 17 (15)' })
    expect(screen.queryByRole('navigation', { name: 'Abschnitte nach Art. 17' })).toBeNull()
    await userEvent.click(toggle)
    const sections = screen.getByRole('navigation', { name: 'Abschnitte nach Art. 17' })
    expect(within(sections).getAllByRole('link')).toHaveLength(15)
  })
})

describe('the Documents screen on a desktop', () => {
  it('has the documents list on the left and first in the reading and tab order', async () => {
    const article = await open(emotionDisclosure('en'), DESKTOP, 'en')
    expect(screen.queryByRole('button', { name: /^Documents \(/ })).toBeNull()
    const list = screen.getByRole('navigation', { name: 'Documents' })
    const interview = screen.getByRole('region', { name: /interview/i })
    expect(list.getBoundingClientRect().right).toBeLessThanOrEqual(
      article.getBoundingClientRect().left,
    )
    expect(precedes(list, article)).toBe(true)
    expect(precedes(list, interview)).toBe(true)
    expect(await firstTabbedInto([list, article, interview])).toBe(list)
  })

  it('has a skeleton\'s numbered sections on the left and first, and the documents list after (DocSkeleton)', async () => {
    const article = await open(
      {
        toolId: DRIVERS,
        name: 'Driver scoring',
        result: PROVIDER_RESULT,
        documents: PROVIDER_DOCUMENTS.list.en.documents,
        template: 'annex_iv_technical_documentation',
        draft: found(
          PROVIDER_DOCUMENTS.en.annex_iv_technical_documentation,
          'annex_iv_technical_documentation',
        ),
      },
      DESKTOP,
      'en',
    )
    const sections = screen.getByRole('navigation', { name: 'Annex IV sections' })
    const documents = screen.getByRole('navigation', { name: 'Documents' })
    const interview = screen.getByRole('region', { name: /interview/i })
    expect(sections.getBoundingClientRect().right).toBeLessThanOrEqual(
      article.getBoundingClientRect().left,
    )
    expect(documents.getBoundingClientRect().top).toBeGreaterThanOrEqual(
      article.getBoundingClientRect().bottom,
    )
    expect(precedes(sections, article)).toBe(true)
    expect(precedes(article, documents)).toBe(true)
    expect(await firstTabbedInto([sections, article, interview, documents])).toBe(sections)
  })
})
