// The result on a phone (artboard `ResultMobile`, P26), in a real browser: one column in the
// desktop's reading order, with the compact law switch under the title and Draft documents full
// width at the end; every touch target at least 44 px; the to-do rows that carry a draft link keep
// the duty readable at 375 px; and an axe pass at 390 px. That no app route scrolls sideways at
// 390 px is checked for every route in components/shells.browser.test.tsx, and for a full result
// in ResultScreen.browser.test.tsx.
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axe from 'axe-core'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'

import { decidedHighRisk, WORKED_EXAMPLE_DESCRIPTION } from '@/test/classify-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { putRun } from './classification-store'

const PHONE = { width: 390, height: 844 } as const
const SMALL_PHONE = { width: 375, height: 812 } as const
const DESKTOP = { width: 1440, height: 1000 } as const
const TOOL_ID = 'applicant-screening'
/** The smallest touch target, in px (WCAG 2.5.5). */
const MIN_TARGET_PX = 44

type Language = 'en' | 'de'

/** The names the phone result is read by, in each language. */
const NAMES = {
  en: {
    back: 'Inventory',
    law: 'Law version',
    amended: 'As amended, 2026',
    original: 'Original, 2024',
    result: 'Result',
    todo: 'What you need to do',
    facts: 'The result rests on',
    steps: 'How Klar got here',
    composer: 'Ask about this result',
    documents: 'Draft documents',
  },
  de: {
    back: 'KI-Inventar',
    law: 'Rechtsstand',
    amended: 'Geändert, 2026',
    original: 'Ursprünglich, 2024',
    result: 'Ergebnis',
    todo: 'Was Sie tun müssen',
    facts: 'Das Ergebnis beruht auf',
    steps: 'So kam Klar zu diesem Ergebnis',
    composer: 'Frage zu diesem Ergebnis',
    documents: 'Dokumente entwerfen',
  },
} as const

async function openResult(
  language: Language,
  viewport: { width: number; height: number } = PHONE,
): Promise<void> {
  await page.viewport(viewport.width, viewport.height)
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  putRun(client, {
    toolId: TOOL_ID,
    name: 'Applicant screening',
    description: WORKED_EXAMPLE_DESCRIPTION,
    result: decidedHighRisk(),
  })
  renderRoute(`/app/inventory/${TOOL_ID}`, client)
  await screen.findByRole('heading', { level: 1, name: 'Applicant screening' })
  await document.fonts.ready
}

/** The result's parts in the order the artboard reads them. */
function sectionsInOrder(language: Language): HTMLElement[] {
  const names = NAMES[language]
  return [
    screen.getByRole('link', { name: names.back }),
    screen.getByRole('heading', { level: 1 }),
    screen.getByRole('group', { name: names.law }),
    screen.getByRole('region', { name: names.result }),
    screen.getByRole('region', { name: names.todo }),
    screen.getByRole('complementary', { name: names.facts }),
    screen.getByRole('region', { name: names.steps }),
    screen.getByRole('textbox', { name: names.composer }),
    screen.getByRole('link', { name: names.documents }),
  ]
}

/** The box a finger can hit: a checkbox's is the label around it. */
function targetBox(element: HTMLElement): DOMRect {
  return (element.closest('label') ?? element).getBoundingClientRect()
}

describe('the result at 390 px', () => {
  it.each(['en', 'de'] as const)(
    'reads in one column in the desktop order (%s)',
    async (language) => {
      await openResult(language)
      const sections = sectionsInOrder(language)
      for (const [index, element] of sections.entries()) {
        const next = sections[index + 1]
        if (!next) break
        const label = `${element.textContent.slice(0, 30)} before ${next.textContent.slice(0, 30)}`
        // In the reading order (the DOM) and on screen: each part wholly below the one before.
        expect(
          element.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING,
          label,
        ).toBeTruthy()
        expect(next.getBoundingClientRect().top, label).toBeGreaterThanOrEqual(
          element.getBoundingClientRect().bottom,
        )
      }
      // Draft documents takes the column's full width.
      const documents = sections.at(-1) as HTMLElement
      const column = documents.parentElement as HTMLElement
      expect(documents.getBoundingClientRect().width).toBe(column.getBoundingClientRect().width)
    },
  )

  it.each(['en', 'de'] as const)(
    'shows the compact law switch once, and Draft documents once (%s)',
    async (language) => {
      await openResult(language)
      const names = NAMES[language]
      // The top bar's switch gives way to the one under the title.
      // Only what is displayed counts: the top bar's switch is display: none, and the header's
      // Draft documents link isn't rendered on a phone (ResultScreen, `!isPhone`).
      const laws = screen.getAllByRole('group', { name: names.law })
      expect(laws).toHaveLength(1)
      within(laws[0] as HTMLElement).getByRole('button', { name: names.amended })
      expect(screen.getAllByRole('link', { name: names.documents })).toHaveLength(1)
    },
  )

  it('switches the law version from the switch under the title', async () => {
    const user = userEvent.setup()
    await openResult('en')
    await user.click(screen.getByRole('button', { name: 'Original, 2024' }))
    expect(screen.getByRole('button', { name: 'Original, 2024' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    // The frame shows the original text's dates and notice (index.css › law-version).
    expect(document.querySelector('.app-frame')).toHaveClass('law-original')
    expect(screen.getByRole('button', { name: 'As amended, 2026' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('opens a step when its row is tapped', async () => {
    const user = userEvent.setup()
    await openResult('en')
    const steps = screen.getByRole('region', { name: 'How Klar got here' })
    const [row] = within(steps).getAllByRole('button', { expanded: false })
    if (!row) throw new Error('no step row')
    await user.click(row)
    expect(row).toHaveAttribute('aria-expanded', 'true')
  })

  it.each(['en', 'de'] as const)(
    'makes every touch target at least 44 px (%s)',
    async (language) => {
      await openResult(language)
      const targets = [
        ...document.querySelectorAll<HTMLElement>('a[href], button, input, textarea, select'),
      ].filter((element) => element.getClientRects().length > 0)
      expect(targets.length).toBeGreaterThan(20)
      const small = targets
        .map((element) => ({ element, box: targetBox(element) }))
        .filter(({ box }) => box.width < MIN_TARGET_PX || box.height < MIN_TARGET_PX)
        .map(
          ({ element, box }) =>
            `${element.tagName} "${element.getAttribute('aria-label') ?? element.textContent}" ${String(Math.round(box.width))}x${String(Math.round(box.height))}`,
        )
      expect(small).toEqual([])
    },
  )

  it.each([
    ['en', 'Show the provision'],
    ['de', 'Vorschrift zeigen'],
  ] as const)(
    'makes a checked step’s provision toggle 44 px tall (%s)',
    async (language, toggle) => {
      await openResult(language)
      const user = userEvent.setup()
      const steps = screen.getByRole('region', { name: NAMES[language].steps })
      await user.click(within(steps).getByRole('button', { name: /^4 / }))
      const button = await within(steps).findByRole('button', { name: toggle })
      expect(targetBox(button).height).toBeGreaterThanOrEqual(MIN_TARGET_PX)
    },
  )

  it('passes axe', async () => {
    await openResult('en')
    // axe-core itself: vitest-axe loads Node modules and doesn't run in the browser project.
    const results = await axe.run(document.body)
    expect(
      results.violations.map(
        (violation) => `${violation.id}: ${violation.nodes.map((node) => node.html).join(' | ')}`,
      ),
    ).toEqual([])
  })
})

describe('the to-do rows at 375 px', () => {
  it.each(['en', 'de'] as const)(
    'keep the duty wide and the draft link clear of the article (%s)',
    async (language) => {
      await openResult(language, SMALL_PHONE)
      const section = screen.getByRole('region', { name: NAMES[language].todo })
      const rows = within(section)
        .getAllByRole('listitem')
        .filter((row) => within(row).queryByRole('link'))
      expect(rows.length).toBeGreaterThan(0)
      for (const row of rows) {
        const link = within(row).getByRole('link')
        const duty = within(row).getByRole('checkbox').closest('label')
          ?.nextElementSibling as HTMLElement
        const reference = within(row).getByText(/^(Art\.|Annex|Anhang)/)
        const linkBox = link.getBoundingClientRect()
        const referenceBox = reference.getBoundingClientRect()
        // The duty keeps most of the row: before the fix it shrank to a one-word column.
        expect(duty.getBoundingClientRect().width, row.textContent).toBeGreaterThan(
          row.getBoundingClientRect().width * 0.6,
        )
        // Under the duty, never beside it.
        expect(linkBox.top, row.textContent).toBeGreaterThanOrEqual(
          duty.getBoundingClientRect().bottom,
        )
        // The article sits after the link with a gap, or on its own line.
        const isOnNextLine = referenceBox.top >= linkBox.bottom
        expect(isOnNextLine || referenceBox.left - linkBox.right >= 8, row.textContent).toBe(true)
      }
    },
  )
})

describe('the result on a desktop', () => {
  it('keeps the switch in the top bar and Draft documents among the actions', async () => {
    await openResult('en', DESKTOP)
    // The sidebar's Inventory link is there; the back link over the title isn't.
    expect(within(screen.getByRole('main')).queryByRole('link', { name: 'Inventory' })).toBeNull()
    const laws = screen.getAllByRole('group', { name: 'Law version' })
    expect(laws).toHaveLength(1)
    const law = laws[0] as HTMLElement
    // The top bar's switch, with the full labels, above the title.
    within(law).getByRole('button', { name: /27 Jul 2026/ })
    const title = screen.getByRole('heading', { level: 1 })
    expect(law.getBoundingClientRect().bottom).toBeLessThanOrEqual(
      title.getBoundingClientRect().top,
    )
    const documents = screen.getByRole('link', { name: 'Draft documents' })
    expect(documents.getBoundingClientRect().bottom).toBeLessThan(
      screen.getByRole('region', { name: 'Result' }).getBoundingClientRect().top,
    )
  })
})
