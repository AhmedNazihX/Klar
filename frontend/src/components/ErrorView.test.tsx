import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import { renderRoute } from '@/test/test-utils'

// The not-found page leads back to the landing page in the visitor's language, so a German visitor
// lost in the app never lands on the English page.
describe('ErrorView', () => {
  it.each([
    ['en', '/no-such-page', 'Back to the start', '/'],
    ['en', '/app/no-such-screen', 'Back to the start', '/'],
    ['de', '/no-such-page', 'Zurück zum Anfang', '/de'],
    ['de', '/app/no-such-screen', 'Zurück zum Anfang', '/de'],
  ] as const)('links home in %s from %s', async (language, path, name, home) => {
    await i18n.changeLanguage(language)
    renderRoute(path)
    expect(await screen.findByRole('link', { name })).toHaveAttribute('href', home)
  })
})
