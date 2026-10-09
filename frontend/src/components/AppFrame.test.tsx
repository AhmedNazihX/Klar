import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import { LOAD_MOTION_MS } from '@/hooks/use-load-motion'
import { stubReducedMotion } from '@/test/reduced-motion'
import { APP_ROUTES } from '@/test/shell-routes'
import { renderRoute } from '@/test/test-utils'

import { LAW_ORIGINAL_CLASS } from './LawSwitch'

const SIDEBAR_EN = ['Inventory', 'Classify a tool', 'Obligations', 'Documents', 'Ask about the Act']
const SIDEBAR_DE = ['KI-Inventar', 'Tool einstufen', 'Pflichten', 'Dokumente', 'Fragen stellen']

async function openApp(path: string, language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const rendered = renderRoute(path)
  await screen.findByRole('heading', { level: 1 })
  return rendered
}

function sidebarLinks(label: string): HTMLElement[] {
  return within(screen.getByRole('navigation', { name: label })).getAllByRole('link')
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('AppFrame sidebar', () => {
  it.each([
    ['en', 'App', SIDEBAR_EN],
    ['de', 'App-Navigation', SIDEBAR_DE],
  ] as const)('shows the five places in order (%s)', async (language, label, names) => {
    await openApp('/app/inventory', language)
    expect(sidebarLinks(label).map((link) => link.textContent)).toEqual(names)
  })

  it('shows the company line, the language switch, the notice and the data links', async () => {
    await openApp('/app/inventory')
    expect(screen.getByText('Your company')).toBeInTheDocument()
    expect(screen.getByText('No company profile yet')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Language' })).toBeInTheDocument()
    expect(
      screen.getByText('You are using an AI system. Results are guidance, not legal advice.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Export data' })).toHaveAttribute(
      'href',
      '/app/your-data',
    )
    expect(screen.getByRole('link', { name: 'Delete my data' })).toHaveAttribute(
      'href',
      '/app/your-data',
    )
  })

  it.each([
    ['/app/inventory', 'Inventory'],
    ['/app/inventory/applicant-screening', 'Inventory'],
    ['/app/classify', 'Classify a tool'],
    ['/app/obligations', 'Obligations'],
    ['/app/documents/annex-iv', 'Documents'],
    ['/app/ask', 'Ask about the Act'],
  ])('marks only the active place on %s', async (path, active) => {
    await openApp(path)
    for (const link of sidebarLinks('App')) {
      if (link.textContent === active) expect(link).toHaveAttribute('aria-current', 'page')
      else expect(link).not.toHaveAttribute('aria-current')
    }
  })

  it('marks no place on screens outside the five (Welcome, Your data)', async () => {
    await openApp('/app/welcome')
    for (const link of sidebarLinks('App')) expect(link).not.toHaveAttribute('aria-current')
  })

  it('moves between screens from the sidebar', async () => {
    const user = userEvent.setup()
    const { router } = await openApp('/app/inventory')
    await user.click(screen.getByRole('link', { name: 'Obligations' }))
    expect(await screen.findByRole('heading', { name: 'Obligations', level: 1 })).toBeVisible()
    expect(router.state.location.pathname).toBe('/app/obligations')
  })
})

describe('AppFrame on every screen', () => {
  it.each(APP_ROUTES)('ends %s with the Notice, in English and German', async (path) => {
    await openApp(path)
    const main = screen.getByRole('main')
    expect(
      within(main).getByText('Guidance, not legal advice. Klar is an AI system.'),
    ).toBeInTheDocument()

    await act(() => i18n.changeLanguage('de'))
    expect(
      within(main).getByText('Orientierungshilfe, keine Rechtsberatung. Klar ist ein KI-System.'),
    ).toBeInTheDocument()
  })

  it('names the screen in the top bar', async () => {
    await openApp('/app/obligations')
    const main = screen.getByRole('main')
    expect(within(main).getAllByText('Obligations')).toHaveLength(2) // the top bar and the h1
  })

  it('opens the app start on Welcome when nothing can be saved (no Supabase)', async () => {
    const { router } = await openApp('/app')
    expect(router.state.location.pathname).toBe('/app/welcome')
  })
})

describe('AppFrame law version', () => {
  it('keeps the law version in the address and across the sidebar', async () => {
    const user = userEvent.setup()
    const { router } = await openApp('/app/inventory')
    const group = screen.getByRole('group', { name: 'Law version' })
    const [amended, original] = within(group).getAllByRole('button')
    expect(amended).toHaveAttribute('aria-pressed', 'true')

    await user.click(original as HTMLElement)

    expect(router.state.location.search).toEqual({ law: 'original' })
    expect(document.querySelector('.app-frame')).toHaveClass(LAW_ORIGINAL_CLASS)
    expect(screen.getByRole('status')).toHaveTextContent(/original 2024 text/)

    await user.click(screen.getByRole('link', { name: 'Documents' }))
    await screen.findByRole('heading', { name: 'Draft documents', level: 1 })
    expect(router.state.location.search).toEqual({ law: 'original' })
    expect(
      within(screen.getByRole('group', { name: 'Law version' })).getAllByRole('button')[1],
    ).toHaveAttribute('aria-pressed', 'true')

    await user.click(
      within(screen.getByRole('group', { name: 'Law version' })).getAllByRole(
        'button',
      )[0] as HTMLElement,
    )
    expect(router.state.location.search).toEqual({})
    expect(document.querySelector('.app-frame')).not.toHaveClass(LAW_ORIGINAL_CLASS)
  })

  it('opens a shared link with the original text selected', async () => {
    await openApp('/app/obligations?law=original')
    const buttons = within(screen.getByRole('group', { name: 'Law version' })).getAllByRole(
      'button',
    )
    expect(buttons[1]).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps the original text notice across a language switch (EN, DE, EN)', async () => {
    const user = userEvent.setup()
    await openApp('/app/obligations?law=original')
    expect(document.querySelector('.app-frame')).toHaveClass(LAW_ORIGINAL_CLASS)

    await user.click(
      within(screen.getByRole('group', { name: 'Language' })).getAllByRole(
        'button',
      )[1] as HTMLElement,
    )
    await screen.findByRole('group', { name: 'Sprache' })
    expect(document.querySelector('.app-frame')).toHaveClass(LAW_ORIGINAL_CLASS)

    await user.click(
      within(screen.getByRole('group', { name: 'Sprache' })).getAllByRole(
        'button',
      )[0] as HTMLElement,
    )
    await screen.findByRole('group', { name: 'Language' })
    expect(document.querySelector('.app-frame')).toHaveClass(LAW_ORIGINAL_CLASS)
  })

  it('keeps the original text notice once the load motion clears', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    await openApp('/app/inventory?law=original')
    act(() => {
      vi.advanceTimersByTime(LOAD_MOTION_MS)
    })
    expect(document.querySelector('.app-frame')).not.toHaveClass('app-intro')
    expect(document.querySelector('.app-frame')).toHaveClass(LAW_ORIGINAL_CLASS)
  })

  it('drops an unknown law version from the address and the links', async () => {
    const { router } = await openApp('/app/inventory?law=bogus')
    const [amended, original] = within(
      screen.getByRole('group', { name: 'Law version' }),
    ).getAllByRole('button')
    expect(amended).toHaveAttribute('aria-pressed', 'true')
    expect(original).toHaveAttribute('aria-pressed', 'false')
    expect(document.querySelector('.app-frame')).not.toHaveClass(LAW_ORIGINAL_CLASS)
    expect(router.state.location.search).toEqual({})
    for (const link of sidebarLinks('App')) {
      expect(link.getAttribute('href')).not.toContain('law=')
    }
  })
})

describe('AppFrame phone menu', () => {
  it('opens the sidebar from Menu and closes it on navigation or Escape', async () => {
    const user = userEvent.setup()
    await openApp('/app/inventory')
    const menu = screen.getByRole('button', { name: 'Menu' })
    const sidebar = document.getElementById(menu.getAttribute('aria-controls') ?? '')
    expect(sidebar).not.toBeNull()
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(sidebar).toHaveClass('hidden')

    await user.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    expect(sidebar).not.toHaveClass('hidden')

    await user.click(screen.getByRole('link', { name: 'Ask about the Act' }))
    await screen.findByRole('heading', { name: 'Ask about the Act', level: 1 })
    expect(menu).toHaveAttribute('aria-expanded', 'false')

    await user.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard('{Escape}')
    expect(menu).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('AppFrame load motion', () => {
  function frame(): Element | null {
    return document.querySelector('.app-frame')
  }
  function screenPanels(): Element | null {
    return document.querySelector('.app-screen')
  }
  function wait(ms: number): void {
    act(() => {
      vi.advanceTimersByTime(ms)
    })
  }

  it('settles the frame and the screen in on load and clears both after 3.5 s', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    await openApp('/app/inventory')
    expect(frame()).toHaveClass('app-intro')
    expect(screenPanels()).toHaveClass('app-screen-intro')

    wait(LOAD_MOTION_MS - 100)
    expect(frame()).toHaveClass('app-intro')
    wait(100)
    expect(frame()).not.toHaveClass('app-intro')
    expect(screenPanels()).not.toHaveClass('app-screen-intro')
  })

  it('moves only the new screen on a navigation, not the frame', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { router } = await openApp('/app/inventory')
    wait(LOAD_MOTION_MS)

    await act(() => router.navigate({ to: '/app/obligations' }))
    await screen.findByRole('heading', { name: 'Obligations', level: 1 })
    expect(frame()).not.toHaveClass('app-intro')
    expect(screenPanels()).toHaveClass('app-screen-intro')
    wait(LOAD_MOTION_MS)
    expect(screenPanels()).not.toHaveClass('app-screen-intro')
  })

  it('moves a screen again when you come back to it (A, B, A)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { router } = await openApp('/app/inventory')
    wait(LOAD_MOTION_MS)
    await act(() => router.navigate({ to: '/app/obligations' }))
    await screen.findByRole('heading', { name: 'Obligations', level: 1 })
    wait(1000)

    await act(() => router.navigate({ to: '/app/inventory' }))
    await screen.findByRole('heading', { name: 'Your AI tools', level: 1 })
    expect(screenPanels()).toHaveClass('app-screen-intro')
  })

  it('never runs with reduced motion', async () => {
    stubReducedMotion(true)
    const { router } = await openApp('/app/inventory')
    expect(frame()).not.toHaveClass('app-intro')
    expect(screenPanels()).not.toHaveClass('app-screen-intro')
    await act(() => router.navigate({ to: '/app/ask' }))
    await screen.findByRole('heading', { name: 'Ask about the Act', level: 1 })
    expect(screenPanels()).not.toHaveClass('app-screen-intro')
  })
})

describe('AppFrame accessibility', () => {
  it('has no detectable accessibility violations', async () => {
    const { container } = await openApp('/app/inventory')
    // jsdom cannot paint, so colour contrast is checked in the browser (P13).
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})
