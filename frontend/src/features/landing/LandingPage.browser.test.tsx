// The landing page in a real browser (Chromium, with index.css and site-motion.css): what is on
// screen at load is never hidden, the layout keeps the artboard's widths and spacing, the timeline
// draws to Today (and on a phone shows Today between the dates), the nav stays pinned and turns
// denser, and reduced motion stops the hero sequence in the stylesheet itself.
import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cdp, page } from 'vitest/browser'
// The Playwright provider types cdp()'s `send` (Chromium's DevTools protocol, to emulate media).
import type {} from '@vitest/browser-playwright'

import { renderRoute, renderWithProviders } from '@/test/test-utils'

import { DatesTimeline } from './DatesTimeline'

const DESKTOP = { width: 1440, height: 900 } as const
const PHONE = { width: 390, height: 844 } as const
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

describe('the timeline on a phone', () => {
  it('shows a visible Today marker between the last date passed and the next', async () => {
    await page.viewport(PHONE.width, PHONE.height)
    // Two dates passed (2 Aug and 2 Dec 2026), two to come.
    renderWithProviders(<DatesTimeline today={new Date('2027-03-01T12:00:00Z')} />)
    await screen.findByRole('heading', { name: 'The dates moved in July 2026.' })
    const items = Array.from(document.querySelectorAll<HTMLElement>('ol > li'))
    const dates = items.filter((item) => !('todayMarker' in item.dataset))
    const lastPast = dates.filter((item) => item.dataset.past === 'true').at(-1)
    const firstComing = dates.find((item) => item.dataset.past !== 'true')
    const today = items.find((item) => 'todayMarker' in item.dataset)
    if (!lastPast || !firstComing || !today) throw new Error('expected Today between two dates')
    expect(today).toHaveTextContent('Today')
    const box = today.getBoundingClientRect()
    // A full-width row, not a stray pill: the chip and its Lens blue rule across the list.
    expect(box.width).toBe(lastPast.getBoundingClientRect().width)
    expect(box.height).toBeGreaterThan(0)
    expect(getComputedStyle(today).visibility).toBe('visible')
    expect(getComputedStyle(today).opacity).toBe('1')
    const rule = today.lastElementChild?.getBoundingClientRect()
    expect(rule?.width).toBeGreaterThan(box.width / 2)
    expect(box.top).toBeGreaterThanOrEqual(lastPast.getBoundingClientRect().bottom)
    expect(box.bottom).toBeLessThanOrEqual(firstComing.getBoundingClientRect().top)
  })
})

describe('the hero sequence with reduced motion', () => {
  afterEach(async () => {
    await cdp().send('Emulation.setEmulatedMedia', { features: [] })
  })

  function introSteps(): HTMLElement[] {
    return Array.from(document.querySelectorAll<HTMLElement>('[data-intro-step]'))
  }

  // The stylesheet's own guard: even with the sequence's attribute set, nothing animates or hides.
  it('runs no step and hides none, in the stylesheet too', async () => {
    await cdp().send('Emulation.setEmulatedMedia', {
      features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
    })
    await open('en')
    const hero = document.getElementById('top')
    if (!hero) throw new Error('no hero')
    expect(hero).not.toHaveAttribute('data-intro')
    hero.setAttribute('data-intro', 'true')
    expect(introSteps().length).toBeGreaterThanOrEqual(11)
    for (const step of introSteps()) {
      const style = getComputedStyle(step)
      expect(style.animationName, step.dataset.introStep).toBe('none')
      expect(style.opacity, step.dataset.introStep).toBe('1')
    }
  })

  // The control: without the preference, the same attribute starts every step's animation.
  it('animates every step without it', async () => {
    await open('en')
    const hero = document.getElementById('top')
    if (!hero) throw new Error('no hero')
    hero.setAttribute('data-intro', 'true')
    for (const step of introSteps()) {
      expect(getComputedStyle(step).animationName, step.dataset.introStep).not.toBe('none')
    }
  })
})
