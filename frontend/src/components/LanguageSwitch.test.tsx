import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { LANGUAGE_STORAGE_KEY } from '@/i18n'
import { renderRoute } from '@/test/test-utils'

describe('LanguageSwitch', () => {
  it('switches the page to German and back', async () => {
    const user = userEvent.setup()
    renderRoute('/')

    expect(
      await screen.findByRole('heading', { name: /Is your AI tool high-risk/ }),
    ).toBeInTheDocument()
    const german = screen.getByRole('button', { name: 'Deutsch' })
    expect(german).toHaveAttribute('aria-pressed', 'false')

    await user.click(german)

    expect(await screen.findByRole('heading', { name: /Ist Ihr KI-Werkzeug/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Deutsch' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('group', { name: 'Sprache' })).toBeInTheDocument()
    expect(screen.getByText(/keine Rechtsberatung/)).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('lang', 'de')
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('de')

    await user.click(screen.getByRole('button', { name: 'English' }))

    expect(
      await screen.findByRole('heading', { name: /Is your AI tool high-risk/ }),
    ).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('lang', 'en')
  })

  it('is reachable and operable with the keyboard', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    await screen.findByRole('heading', { level: 1 })

    await user.tab() // the logo link
    await user.tab()
    expect(screen.getByRole('button', { name: 'English' })).toHaveFocus()
    await user.tab()
    await user.keyboard('{Enter}')

    expect(await screen.findByRole('heading', { name: /Ist Ihr KI-Werkzeug/ })).toBeInTheDocument()
  })
})
