import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { LANGUAGE_STORAGE_KEY } from '@/i18n'
import { renderRoute } from '@/test/test-utils'

describe('LanguageSwitch', () => {
  // On a site page, so the switch only changes the language (on the landing page it also moves
  // between / and /de: SiteFrame.test.tsx).
  it('switches the page to German and back', async () => {
    const user = userEvent.setup()
    renderRoute('/method')

    expect(await screen.findByRole('heading', { name: 'How Klar is measured' })).toBeInTheDocument()
    const german = screen.getByRole('button', { name: 'Deutsch' })
    expect(german).toHaveAttribute('aria-pressed', 'false')

    await user.click(german)

    expect(
      await screen.findByRole('heading', { name: 'So wird Klar gemessen' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Deutsch' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('group', { name: 'Sprache' })).toBeInTheDocument()
    expect(screen.getByText(/keine Rechtsberatung/)).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('lang', 'de')
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('de')

    await user.click(screen.getByRole('button', { name: 'English' }))

    expect(await screen.findByRole('heading', { name: 'How Klar is measured' })).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('lang', 'en')
  })

  it('is reachable and operable with the keyboard', async () => {
    const user = userEvent.setup()
    renderRoute('/method')
    await screen.findByRole('heading', { level: 1 })

    // The site nav: the logo, then the four section links.
    for (let step = 0; step < 5; step += 1) await user.tab()
    await user.tab()
    expect(screen.getByRole('button', { name: 'English' })).toHaveFocus()
    await user.tab()
    await user.keyboard('{Enter}')

    expect(
      await screen.findByRole('heading', { name: 'So wird Klar gemessen' }),
    ).toBeInTheDocument()
  })
})
