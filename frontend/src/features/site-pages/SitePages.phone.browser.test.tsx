// The site pages on a phone, in a real browser (Chromium, with index.css and the self-hosted
// fonts): Contact's three topics stack in full view, each a 44 px target, and a long German title
// ("Datenschutzerklärung") stays inside the 16 px gutter down to 360 px. That no site page scrolls
// sideways at 390 px is checked for every route in components/shells.browser.test.tsx.
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { describe, expect, it, vi } from 'vitest'
import { page } from 'vitest/browser'

import { renderRoute } from '@/test/test-utils'

type Language = 'en' | 'de'

const PHONE = { width: 390, height: 844 } as const
const SMALL_PHONE = { width: 360, height: 780 } as const
/** The site frame's side gutter on a phone, in px. */
const GUTTER_PX = 16
/** The smallest touch target, in px (WCAG 2.5.5). */
const MIN_TARGET_PX = 44
const FIRST_LOAD_MS = 8000
/** How far the pill may sit from its button on each side, in px (offset* values are rounded). */
const PILL_TOLERANCE_PX = 1

const TOPICS: Record<Language, { group: string; topics: string[] }> = {
  en: {
    group: 'What is it about?',
    topics: ['A question about Klar', 'Feedback', 'Privacy request'],
  },
  de: { group: 'Worum geht es?', topics: ['Eine Frage zu Klar', 'Feedback', 'Datenschutzanfrage'] },
}

async function open(path: string, language: Language): Promise<void> {
  await i18n.changeLanguage(language)
  renderRoute(path)
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_LOAD_MS })
  await document.fonts.ready
}

/** True when `box` lies wholly inside the window, sideways and down to the gutter. */
function isInsideGutter(box: DOMRect): boolean {
  return box.left >= GUTTER_PX && box.right <= window.innerWidth - GUTTER_PX
}

/** The painted box of an element's text, which may reach past the element when a word can't break. */
function textBox(element: HTMLElement): DOMRect {
  const range = document.createRange()
  range.selectNodeContents(element)
  return range.getBoundingClientRect()
}

describe.each(['en', 'de'] as const)('the site pages on a phone (%s)', (language) => {
  it('shows all three Contact topics at 390 px, each a 44 px target, and switches them', async () => {
    await page.viewport(PHONE.width, PHONE.height)
    await open('/contact', language)
    const { group, topics } = TOPICS[language]
    const control = screen.getByRole('group', { name: group })
    const buttons = within(control).getAllByRole('button')
    expect(buttons.map((button) => button.textContent)).toEqual(topics)
    for (const button of buttons) {
      const box = button.getBoundingClientRect()
      expect(isInsideGutter(box)).toBe(true)
      expect(box.height).toBeGreaterThanOrEqual(MIN_TARGET_PX)
      // The label itself is not clipped inside its button.
      expect(button.scrollWidth).toBeLessThanOrEqual(button.clientWidth)
      expect(isInsideGutter(textBox(button))).toBe(true)
    }
    // Nothing in the row scrolls sideways out of sight.
    expect(control.scrollWidth).toBeLessThanOrEqual(control.clientWidth)

    const user = userEvent.setup()
    const last = buttons.at(-1)
    if (!last) throw new Error('The topic switch has no buttons.')
    await user.click(last)
    expect(last).toHaveAttribute('aria-pressed', 'true')
    expect(buttons[0]).toHaveAttribute('aria-pressed', 'false')
    // The white pill settles on the chosen topic, in the stacked layout too.
    const pill = control.querySelector<HTMLElement>('span[aria-hidden="true"]')
    if (!pill) throw new Error('The topic switch has no pill.')
    // The pill is placed from rounded offset* values, so each side may be off by a sub-pixel.
    await vi.waitFor(() => {
      const [from, to] = [pill.getBoundingClientRect(), last.getBoundingClientRect()]
      for (const side of ['top', 'right', 'bottom', 'left'] as const) {
        expect(Math.abs(from[side] - to[side])).toBeLessThanOrEqual(PILL_TOLERANCE_PX)
      }
    })
  })
})

describe.each([PHONE, SMALL_PHONE])('the German privacy title at $width px', (viewport) => {
  it('stays inside the gutter', async () => {
    await page.viewport(viewport.width, viewport.height)
    await open('/privacy', 'de')
    const title = screen.getByRole('heading', { level: 1, name: /Datenschutz/ })
    expect(isInsideGutter(textBox(title))).toBe(true)
    expect(document.documentElement.scrollWidth).toBe(document.documentElement.clientWidth)
  })
})
