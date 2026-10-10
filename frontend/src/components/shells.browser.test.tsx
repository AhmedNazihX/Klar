// The shells' layout in a real browser (Chromium, with index.css and the self-hosted fonts):
// nothing scrolls sideways on a 390 px phone, the German sidebar labels fit 220 px, and the load
// motion's selectors (index.css › app-load) reach the right panels.
import { act, screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { page } from 'vitest/browser'

import { APP_ROUTES, SITE_ROUTES } from '@/test/shell-routes'
import { renderRoute } from '@/test/test-utils'
import { FIRST_RENDER_MS } from '@/test/user-data-handlers'

import { LOAD_MOTION_MS } from '@/hooks/use-load-motion'

import { SIDEBAR_ITEM_WIDTH_PX } from './app-nav'

const PHONE = { width: 390, height: 844 } as const
const DESKTOP = { width: 1440, height: 1000 } as const

async function open(path: string, language: 'en' | 'de'): Promise<void> {
  await i18n.changeLanguage(language)
  renderRoute(path)
  // The file's first test (`/app/welcome (en)`) loads the frame and its lazy route chunks cold,
  // which takes past the default second when another run shares the machine (F10).
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_RENDER_MS })
  await document.fonts.ready
}

/** How far the page reaches past the window's right edge, in px (0 when nothing sticks out). */
function sidewaysOverflow(): number {
  const root = document.documentElement
  return root.scrollWidth - root.clientWidth
}

describe('at 390 px', () => {
  const routes = [...APP_ROUTES, ...SITE_ROUTES]
  it.each(routes.flatMap((path) => [[path, 'en'] as const, [path, 'de'] as const]))(
    '%s (%s) does not scroll sideways',
    async (path, language) => {
      await page.viewport(PHONE.width, PHONE.height)
      await open(path, language)
      expect(sidewaysOverflow()).toBe(0)
    },
  )

  it('shows the phone top bar instead of the sidebar, and the sidebar from Menu', async () => {
    await page.viewport(PHONE.width, PHONE.height)
    await open('/app/inventory', 'de')
    expect(screen.queryByRole('navigation', { name: 'App-Navigation' })).toBeNull()
    screen.getByRole('button', { name: 'Menü' }).click()
    expect(await screen.findByRole('navigation', { name: 'App-Navigation' })).toBeVisible()
    expect(sidewaysOverflow()).toBe(0)
  })
})

describe('on a desktop', () => {
  it('places the 248 px sidebar 24 px from the window', async () => {
    await page.viewport(DESKTOP.width, DESKTOP.height)
    await open('/app/inventory', 'en')
    const sidebar = screen.getByRole('navigation', { name: 'App' }).closest('aside')
    const box = sidebar?.getBoundingClientRect()
    expect(box?.left).toBe(24)
    expect(box?.top).toBe(24)
    expect(box?.width).toBe(248)
    expect(screen.queryByRole('button', { name: 'Menu' })).toBeNull()
  })

  it.each(['en', 'de'] as const)('fits every %s sidebar label in 220 px', async (language) => {
    await page.viewport(DESKTOP.width, DESKTOP.height)
    await open('/app/inventory', language)
    const nav = screen.getByRole('navigation', {
      name: language === 'de' ? 'App-Navigation' : 'App',
    })
    for (const link of within(nav).getAllByRole('link')) {
      // The item is at most 220 px wide (the sidebar less its padding and 1 px rims), and its
      // content (padding, icon, gap, label) fits inside it without overflowing.
      expect(link.getBoundingClientRect().width, link.textContent).toBeLessThanOrEqual(
        SIDEBAR_ITEM_WIDTH_PX,
      )
      expect(link.scrollWidth, link.textContent).toBeLessThanOrEqual(link.clientWidth)
      expect(getComputedStyle(link).fontSize).toBe('15px')
    }
  })
})

describe('the load motion', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  // The frame's top bar, and the first of the screen's own panels.
  function animationOf(selector: string): string {
    const element = document.querySelector(selector)
    if (!element) throw new Error(`${selector} is not on the page`)
    return getComputedStyle(element).animationName
  }
  const TOP_BAR = '.app-column > :first-child'
  const FIRST_PANEL = '.app-screen > :first-child'

  it('moves the frame and the screen on load, then only the new screen on a navigation', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    await page.viewport(DESKTOP.width, DESKTOP.height)
    await i18n.changeLanguage('en')
    const { router } = renderRoute('/app/inventory')
    await screen.findByRole('heading', { level: 1 })
    expect(animationOf(TOP_BAR)).toBe('app-rise')
    expect(animationOf(FIRST_PANEL)).toBe('app-rise')

    act(() => {
      vi.advanceTimersByTime(LOAD_MOTION_MS)
    })
    expect(animationOf(TOP_BAR)).toBe('none')
    expect(animationOf(FIRST_PANEL)).toBe('none')

    await act(() => router.navigate({ to: '/app/obligations' }))
    await screen.findByRole('heading', { name: 'Obligations', level: 1 })
    expect(animationOf(FIRST_PANEL)).toBe('app-rise')
    expect(animationOf(TOP_BAR)).toBe('none')
  })
})
