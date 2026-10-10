// The landing page in a real browser (Chromium, with index.css and site-motion.css): what is on
// screen at load is never hidden, the layout keeps the artboard's widths and spacing, the timeline
// draws to Today, and the nav stays pinned and turns denser.
import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it, vi } from 'vitest'
import { page } from 'vitest/browser'

import { renderRoute } from '@/test/test-utils'

const DESKTOP = { width: 1440, height: 900 } as const
// Tall enough that the dates panel (a Reveal) is on screen at load, below the hero.
const TALL = { width: 1440, height: 1600 } as const
// The first test loads the page's code-split chunk, which can take a few seconds.
const FIRST_LOAD_MS = 8000

async function open(
  language: 'en' | 'de',
  size: { width: number; height: number } = DESKTOP,
): Promise<void> {
  await page.viewport(size.width, size.height)
  window.scrollTo(0, 0)
  await i18n.changeLanguage(language)
  renderRoute(language === 'de' ? '/de' : '/')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_LOAD_MS })
  await document.fonts.ready
}

function isOnScreen(element: Element): boolean {
  const box = element.getBoundingClientRect()
  return box.bottom > 0 && box.top < window.innerHeight && box.height > 0
}

function reveals(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'))
}

describe.each(['en', 'de'] as const)('at load (%s)', (language) => {
  it('never hides an element that starts on screen', async () => {
    await open(language, TALL)
    // The observers have answered once every element off screen is waiting.
    await vi.waitFor(() => {
      expect(reveals().filter((element) => !isOnScreen(element)).length).toBeGreaterThan(0)
      for (const element of reveals().filter((item) => !isOnScreen(item))) {
        expect(element).toHaveAttribute('data-reveal-at')
      }
    })
    const onScreen = reveals().filter(isOnScreen)
    expect(onScreen.length).toBeGreaterThan(0)
    for (const element of onScreen) {
      expect(element, element.textContent).not.toHaveAttribute('data-reveal-at')
      expect(getComputedStyle(element).opacity).toBe('1')
    }
  })
})

describe('the layout', () => {
  it('keeps the content 1248 px wide, 96 px after the hero and 128 px between sections', async () => {
    await open('en')
    const sections = Array.from(document.querySelectorAll('main section'))
      .filter((section) => section.parentElement?.closest('section') === null)
      .map((section) => section.getBoundingClientRect())
    expect(sections).toHaveLength(8)
    expect(sections[0]?.width).toBe(1248)
    const gaps = sections.slice(1).map((box, index) => box.top - (sections[index]?.bottom ?? 0))
    expect(gaps).toEqual([96, 128, 128, 128, 128, 128, 128])
  })

  it('draws the timeline line to the Today marker', async () => {
    await open('en')
    const fill = screen.getByTestId('timeline-fill')
    // The chip on the line (the phone's copy in the list is hidden at this width).
    const chip = document.querySelector('.timeline-today')
    if (!chip) throw new Error('no Today marker on the line')
    fill.scrollIntoView({ block: 'center' })
    const chipBox = chip.getBoundingClientRect()
    const chipCentre = chipBox.left + chipBox.width / 2
    // Measured once the panel has arrived and the line has drawn (1.3 s after a 0.35 s pause).
    await vi.waitFor(
      () => {
        expect(Math.abs(fill.getBoundingClientRect().right - chipCentre)).toBeLessThanOrEqual(1)
      },
      { timeout: 4000 },
    )
    window.scrollTo(0, 0)
  })

  it('keeps the nav pinned on top and denser once the page scrolls', async () => {
    await open('en')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(nav.getBoundingClientRect().height).toBe(68)
    window.scrollTo(0, 1500)
    await vi.waitFor(() => {
      expect(nav).toHaveAttribute('data-dense', 'true')
      expect(nav.getBoundingClientRect().height).toBe(60)
    })
    expect(nav.getBoundingClientRect().top).toBe(24)
    window.scrollTo(0, 0)
  })
})
