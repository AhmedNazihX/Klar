import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { Notice } from './Notice'

describe('Notice', () => {
  it('says both halves in micro type: guidance, not legal advice, and an AI system', async () => {
    renderWithProviders(<Notice />)
    expect(
      await screen.findByText('Guidance, not legal advice. Klar is an AI system.'),
    ).toHaveClass('text-micro', 'text-slate')
  })

  it('speaks German', async () => {
    await i18n.changeLanguage('de')
    renderWithProviders(<Notice />)
    expect(
      await screen.findByText('Orientierungshilfe, keine Rechtsberatung. Klar ist ein KI-System.'),
    ).toBeInTheDocument()
  })
})
