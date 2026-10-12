import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import { WORKED_EXAMPLE } from '@/test/classify-fixtures'
import { renderWithProviders } from '@/test/test-utils'

import { Citation } from './Citation'

const ENGLISH_QUOTE = "'AI system' means a machine-based system …"
const ENGLISH_ONLY_TAG = 'Amtlicher Text nur auf Englisch verfügbar'

describe('Citation', () => {
  it('quotes the provision in the serif, adds the quotation marks and names the source', async () => {
    renderWithProviders(
      <Citation language="en" source="Art. 3(1), Regulation (EU) 2024/1689, English">
        {ENGLISH_QUOTE}
      </Citation>,
    )
    const quote = await screen.findByText(`“${ENGLISH_QUOTE}”`)
    expect(quote.closest('blockquote')).toHaveClass('font-serif', 'text-quote')
    expect(quote.closest('blockquote')).toHaveAttribute('lang', 'en')
    expect(screen.getByText('Art. 3(1), Regulation (EU) 2024/1689, English')).toBeInTheDocument()
  })

  it('does not tag an English quote on an English screen', async () => {
    renderWithProviders(<Citation language="en">{ENGLISH_QUOTE}</Citation>)
    await screen.findByText(`“${ENGLISH_QUOTE}”`)
    expect(screen.queryByText(ENGLISH_ONLY_TAG)).not.toBeInTheDocument()
    expect(screen.queryByText('Official text available in English only')).not.toBeInTheDocument()
  })

  it('keeps an English-only quote in English on a German screen, with the tag and a German line', async () => {
    await i18n.changeLanguage('de')
    renderWithProviders(<Citation language="en">{ENGLISH_QUOTE}</Citation>)

    const quote = await screen.findByText(`“${ENGLISH_QUOTE}”`)
    expect(quote.closest('blockquote')).toHaveAttribute('lang', 'en')
    expect(screen.getByText(ENGLISH_ONLY_TAG)).toBeInTheDocument()
    expect(screen.getByText(/keine amtliche deutsche Fassung/)).toBeInTheDocument()
  })

  it('quotes the official German text on a German screen with German marks and no tag', async () => {
    await i18n.changeLanguage('de')
    renderWithProviders(<Citation language="de">Wortlaut</Citation>)
    expect(await screen.findByText('„Wortlaut“')).toBeInTheDocument()
    expect(screen.queryByText(ENGLISH_ONLY_TAG)).not.toBeInTheDocument()
  })

  it.each([
    // Art. 3 Nr. 4 opens with its own quoted term: one „ … “ pair, nothing added.
    [
      'de',
      '„Betreiber“ eine natürliche oder juristische Person',
      '„Betreiber“ eine natürliche oder juristische Person',
    ],
    ['de', 'die als „Betreiber“ gilt“', '„die als „Betreiber“ gilt“'],
    // Ending on an inner quoted term still gets the outer close.
    ['de', 'eine Person gilt als „Betreiber“', '„eine Person gilt als „Betreiber““'],
    [
      'en',
      '“deployer” means a natural or legal person',
      '“deployer” means a natural or legal person',
    ],
    ['en', 'such a person is a “deployer”', '“such a person is a “deployer””'],
  ] as const)(
    'does not double a quotation mark the %s text already has: %s',
    async (language, text, shown) => {
      await i18n.changeLanguage(language)
      renderWithProviders(<Citation language={language}>{text}</Citation>)
      const quote = await screen.findByText(shown)
      expect(quote.closest('blockquote')).toBeInTheDocument()
    },
  )
})

function recordedQuote(provisionId: string): string {
  const citation = WORKED_EXAMPLE.steps
    .flatMap((step) => step.citations ?? [])
    .find((candidate) => candidate.provision_id === provisionId)
  if (!citation) throw new Error(`The worked example quotes ${provisionId}.`)
  return citation.quote
}

/** The quote's words as shown, without the quotation marks and the ellipsis. */
function shownWords(element: Element): string {
  return element.textContent.replace(/^[“„]/, '').replace(/ …[”“]$/, '')
}

describe('Citation, a long quote', () => {
  // The worked example's Transparency step quotes all of Art. 50 (4,740 characters).
  const ART_50 = recordedQuote('art:50')

  it.each([
    ['en', 'Show full text', 'Show less'],
    ['de', 'Ganzen Text zeigen', 'Weniger zeigen'],
  ] as const)(
    'shows its opening with an ellipsis and a toggle for the full text (%s)',
    async (language, show, hide) => {
      await i18n.changeLanguage(language)
      const user = userEvent.setup()
      renderWithProviders(<Citation language="en">{ART_50}</Citation>)

      const toggle = await screen.findByRole('button', { name: show })
      expect(toggle).toHaveAttribute('aria-expanded', 'false')
      // The quote's text as rendered, exactly (the recorded quote keeps its line breaks).
      const quoteText = () => screen.getByRole('blockquote').textContent
      expect(quoteText()).toMatch(/ …”$/)
      const preview = shownWords(screen.getByRole('blockquote'))
      // Cut at a word boundary, the words unchanged: an opening of the official text.
      expect(ART_50.startsWith(preview)).toBe(true)
      expect(ART_50.charAt(preview.length)).toBe(' ')
      expect(preview.length).toBeLessThan(ART_50.length)

      toggle.focus()
      await user.keyboard('{Enter}')
      expect(quoteText()).toBe(`“${ART_50}”`)
      const expanded = screen.getByRole('button', { name: hide })
      expect(expanded).toHaveAttribute('aria-expanded', 'true')
      expect(expanded).toHaveAttribute('aria-controls', screen.getByRole('blockquote').id)

      await user.click(expanded)
      expect(quoteText()).toBe(`“${preview} …”`)
      expect(screen.getByRole('button', { name: show })).toHaveAttribute('aria-expanded', 'false')
    },
  )

  it('leaves a short quote whole, with no toggle', async () => {
    const definition = recordedQuote('art:3:1')
    renderWithProviders(<Citation language="en">{definition}</Citation>)
    expect((await screen.findByRole('blockquote')).textContent).toBe(`“${definition}”`)
    expect(screen.queryByRole('button')).toBeNull()
  })
})
