import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { EvidenceTag } from './EvidenceTag'

describe('EvidenceTag', () => {
  it('names where a fact came from, with a glyph that carries the meaning', async () => {
    renderWithProviders(
      <>
        <EvidenceTag kind="stated" />
        <EvidenceTag kind="inferred" />
        <EvidenceTag kind="assumed" />
      </>,
    )
    const stated = await screen.findByText('Stated')
    const inferred = screen.getByText('Inferred')
    const assumed = screen.getByText('Assumed')

    // Filled dot, half dot, ring: the glyphs differ in shape, not colour.
    expect(stated.querySelector('circle')).toHaveAttribute('fill', 'currentColor')
    expect(inferred.querySelector('path')).not.toBeNull()
    expect(assumed.querySelector('circle')).toHaveAttribute('fill', 'none')
    expect(assumed.querySelector('path')).toBeNull()
    for (const tag of [stated, inferred, assumed]) {
      expect(tag.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
      expect(tag).toHaveClass('rounded-tag', 'text-ink-2')
    }
  })

  it('speaks German', async () => {
    await i18n.changeLanguage('de')
    renderWithProviders(<EvidenceTag kind="assumed" />)
    expect(await screen.findByText('Angenommen')).toHaveAttribute('data-evidence', 'assumed')
  })
})
