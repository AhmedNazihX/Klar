import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import { markedPlaceholders, unmarkedPlaceholders } from '@/test/placeholders'
import { renderRoute } from '@/test/test-utils'

type Language = 'en' | 'de'

const FIRST_LOAD_MS = 8000

async function openImpressum(language: Language) {
  await i18n.changeLanguage(language)
  const rendered = renderRoute('/impressum')
  await screen.findByRole('heading', { level: 1 }, { timeout: FIRST_LOAD_MS })
  return rendered
}

// The Impressum is German on both language versions; only the template note follows the page.
const SECTIONS = ['Anbieter', 'Kontakt', 'Weitere Angaben', 'Hinweis'] as const
const FIELDS = [
  ['Name', '[NAME / FIRMA]'],
  ['Anschrift', '[STRASSE, PLZ ORT]'],
  ['Vertreten durch', '[NAME, FALLS JURISTISCHE PERSON]'],
  ['E-Mail', '[E-MAIL]'],
  ['Telefon', '[TELEFON]'],
  ['Umsatzsteuer-ID', '[FALLS VORHANDEN]'],
  ['Registereintrag', '[FALLS VORHANDEN]'],
] as const
// Dropped (user 2026-10-10): Klar has no journalistic-editorial content, so § 18 Abs. 2 MStV
// doesn't apply.
const DROPPED_FIELD = 'Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV'
const GERMAN_LEAD = 'Angaben gemäß § 5 DDG.'
const NOTE =
  'Klar bietet eine Orientierungshilfe zur KI-Verordnung, keine Rechtsberatung. Klar ist selbst ein KI-System.'
const INTRO: Record<Language, { lead: string; template: string }> = {
  en: {
    lead: 'Legal notice. Angaben gemäß § 5 DDG.',
    template: 'Template. Fill in every bracketed field before launch.',
  },
  de: {
    lead: 'Angaben gemäß § 5 DDG.',
    template: 'Vorlage. Vor dem Start jedes Feld in eckigen Klammern ausfüllen.',
  },
}

describe.each(['en', 'de'] as const)('the Impressum (%s)', (language) => {
  it('shows the German sections and fields, marked as German', async () => {
    await openImpressum(language)
    const title = screen.getByRole('heading', { level: 1 })
    expect(title).toHaveTextContent('Impressum')
    expect(title).toHaveAttribute('lang', 'de')
    // Only the German phrase is marked German: the English "Legal notice." keeps the page's language.
    const german = screen.getByText(GERMAN_LEAD)
    expect(german).toHaveAttribute('lang', 'de')
    const lead = german.closest('p')
    expect(lead?.textContent).toBe(INTRO[language].lead)
    expect(lead).not.toHaveAttribute('lang')
    expect(lead?.parentElement).not.toHaveAttribute('lang')
    expect(screen.getByRole('note')).toHaveTextContent(INTRO[language].template)
    const main = screen.getByRole('main')
    const sections = within(main).getAllByRole('region')
    expect(sections.map((section) => section.getAttribute('lang'))).toEqual(
      SECTIONS.map(() => 'de'),
    )
    expect(
      within(main)
        .getAllByRole('heading', { level: 2 })
        .map((heading) => heading.textContent),
    ).toEqual(SECTIONS)
    for (const [label, placeholder] of FIELDS) {
      const term = within(main).getByText(label, { selector: 'dt' })
      expect(term.nextElementSibling).toHaveTextContent(placeholder)
    }
    expect(screen.getByText(NOTE)).toBeInTheDocument()
    expect(screen.queryByText(DROPPED_FIELD)).toBeNull()
    expect(screen.queryByText('[NAME, ANSCHRIFT]')).toBeNull()
  })

  it('marks every unknown as a placeholder', async () => {
    await openImpressum(language)
    const main = screen.getByRole('main')
    expect(unmarkedPlaceholders(main)).toEqual([])
    expect(markedPlaceholders(main)).toEqual(FIELDS.map(([, placeholder]) => placeholder))
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = await openImpressum(language)
    // jsdom cannot paint, so colour contrast is checked in the browser.
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})
