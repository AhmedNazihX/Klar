import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import { SITE_ROUTES } from '@/test/shell-routes'
import { renderRoute } from '@/test/test-utils'

async function openSite(path: string, language: 'en' | 'de' = 'en') {
  await i18n.changeLanguage(language)
  const rendered = renderRoute(path)
  await screen.findByRole('heading', { level: 1 })
  return rendered
}

function footer(): HTMLElement {
  return screen.getByRole('contentinfo')
}

// The footer's data line, exactly (user-approved 2026-10-10): the Nebius region is unconfirmed
// (decision 005), so it names the host without claiming the EU.
const FOOTER_DATA = {
  en:
    'Klar is itself an AI system, and tells you so on every screen. Your descriptions stay in your ' +
    'own anonymous session and are deleted after 30 days without activity. Models are reached ' +
    'through OpenRouter; embeddings run on Nebius (region to be confirmed). Full list of providers ' +
    'in the privacy notice.',
  de:
    'Klar ist selbst ein KI-System und sagt das auf jedem Bildschirm. Ihre Beschreibungen bleiben ' +
    'in Ihrer anonymen Sitzung und werden nach 30 Tagen ohne Aktivität gelöscht. Die Modelle ' +
    'werden über OpenRouter angesprochen; Embeddings laufen bei Nebius (Region noch zu ' +
    'bestätigen). Alle Anbieter stehen in der Datenschutzerklärung.',
} as const

describe('SiteNav', () => {
  it.each([
    ['en', 'Main', ['How it works', 'Accuracy', 'For AI agents', 'Your data'], 'Classify a tool'],
    [
      'de',
      'Hauptnavigation',
      ['So funktioniert es', 'Genauigkeit', 'Für KI-Agenten', 'Ihre Daten'],
      'Tool einstufen',
    ],
  ] as const)(
    'shows the four links, EN/DE and the action (%s)',
    async (language, label, links, action) => {
      await openSite('/method', language)
      const nav = within(screen.getByRole('navigation', { name: label }))
      for (const name of links) expect(nav.getByRole('link', { name })).toBeInTheDocument()
      expect(nav.getByRole('button', { name: 'English' })).toBeInTheDocument()
      expect(nav.getByRole('button', { name: 'Deutsch' })).toBeInTheDocument()
      expect(nav.getByRole('link', { name: action })).toHaveAttribute('href', '/app')
    },
  )

  it('points the section links at the landing page of the current language', async () => {
    await openSite('/method', 'de')
    expect(screen.getByRole('link', { name: 'So funktioniert es' })).toHaveAttribute(
      'href',
      '/de#how',
    )
    expect(screen.getByRole('link', { name: 'Ihre Daten' })).toHaveAttribute('href', '/privacy')
  })

  it('moves between the English and German landing pages with EN/DE', async () => {
    const user = userEvent.setup()
    const { router } = await openSite('/')
    await user.click(screen.getByRole('button', { name: 'Deutsch' }))
    expect(router.state.location.pathname).toBe('/de')
    await user.click(screen.getByRole('button', { name: 'English' }))
    expect(router.state.location.pathname).toBe('/')
  })

  it('stays on a site page when the language changes', async () => {
    const user = userEvent.setup()
    const { router } = await openSite('/privacy')
    await user.click(screen.getByRole('button', { name: 'Deutsch' }))
    expect(router.state.location.pathname).toBe('/privacy')
    expect(await screen.findByRole('heading', { name: 'Datenschutzerklärung' })).toBeVisible()
  })

  it('opens /de in German', async () => {
    await openSite('/de')
    expect(i18n.resolvedLanguage).toBe('de')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Wo steht Ihr KI‑Tool')
  })
})

describe('SiteFooter', () => {
  it('says data is deleted after 30 days without activity (EN)', async () => {
    await openSite('/method')
    const end = within(footer())
    expect(end.getByText('Guidance, not legal advice.')).toBeInTheDocument()
    expect(end.getByText(FOOTER_DATA.en)).toBeInTheDocument()
  })

  it('says nach 30 Tagen ohne Aktivität (DE)', async () => {
    await openSite('/method', 'de')
    const end = within(footer())
    expect(end.getByText('Orientierungshilfe, keine Rechtsberatung.')).toBeInTheDocument()
    expect(end.getByText(FOOTER_DATA.de)).toBeInTheDocument()
  })

  it('links the four site pages', async () => {
    await openSite('/')
    const end = within(footer())
    expect(end.getByRole('link', { name: 'How it’s measured' })).toHaveAttribute('href', '/method')
    expect(end.getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy')
    expect(end.getByRole('link', { name: 'Impressum' })).toHaveAttribute('href', '/impressum')
    expect(end.getByRole('link', { name: 'Impressum' })).toHaveAttribute('lang', 'de')
    expect(end.getByRole('link', { name: 'Contact' })).toHaveAttribute('href', '/contact')
  })

  it.each(SITE_ROUTES)('ends %s with the guidance and the AI notice', async (path) => {
    await openSite(path)
    const isGerman = path === '/de'
    const end = within(footer())
    expect(
      end.getByText(
        isGerman ? 'Orientierungshilfe, keine Rechtsberatung.' : 'Guidance, not legal advice.',
      ),
    ).toBeInTheDocument()
    expect(
      end.getByText(isGerman ? /Klar ist selbst ein KI-System/ : /Klar is itself an AI system/),
    ).toBeInTheDocument()
  })

  it('follows a language change', async () => {
    await openSite('/contact')
    await act(() => i18n.changeLanguage('de'))
    expect(within(footer()).getByText(/nach 30 Tagen ohne Aktivität/)).toBeInTheDocument()
  })
})

describe('SiteFrame', () => {
  it('sits on the MistGround', async () => {
    const { container } = await openSite('/privacy')
    expect(container.querySelector('[data-ground="mist"]')).toHaveClass('bg-ground')
  })

  it('shows unknown addresses on the site frame', async () => {
    await openSite('/no-such-page')
    expect(screen.getByText('This page does not exist.')).toBeInTheDocument()
    expect(footer()).toBeInTheDocument()
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = await openSite('/method')
    // jsdom cannot paint, so colour contrast is checked in the browser (P13).
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})
