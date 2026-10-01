import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

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
})
