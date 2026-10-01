import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { GlassPanel } from './GlassPanel'

describe('GlassPanel', () => {
  it('is padded glass with the card radius by default', async () => {
    renderWithProviders(<GlassPanel>Panel</GlassPanel>)
    const panel = await screen.findByText('Panel')
    expect(panel).toHaveClass('glass', 'rounded-card', 'p-7')
    expect(panel).not.toHaveClass('glint', 'lift')
  })

  it('takes the thin and dark tones, the system radii and an element', async () => {
    renderWithProviders(
      <>
        <GlassPanel tone="thin" radius="small" padded={false}>
          Thin
        </GlassPanel>
        <GlassPanel as="section" tone="dark" radius="feature" aria-label="Code">
          Dark
        </GlassPanel>
      </>,
    )
    const thin = await screen.findByText('Thin')
    expect(thin).toHaveClass('glass-thin', 'rounded-card-small')
    expect(thin).not.toHaveClass('p-7')
    const dark = screen.getByRole('region', { name: 'Code' })
    expect(dark).toHaveClass('glass-dark', 'rounded-feature')
  })

  it('lets a later padding win over the default', async () => {
    renderWithProviders(<GlassPanel className="p-8">Roomy</GlassPanel>)
    const panel = await screen.findByText('Roomy')
    expect(panel).toHaveClass('p-8')
    expect(panel).not.toHaveClass('p-7')
  })

  it('moves the glint with the pointer and lifts when asked', async () => {
    renderWithProviders(
      <GlassPanel glint lift>
        Card
      </GlassPanel>,
    )
    const panel = await screen.findByText('Card')
    expect(panel).toHaveClass('glint', 'lift')

    fireEvent.pointerMove(panel, { clientX: 40, clientY: 30 })

    expect(panel.style.getPropertyValue('--mx')).toBe('40px')
    expect(panel.style.getPropertyValue('--my')).toBe('30px')
  })

  it('leaves the light still without glint', async () => {
    renderWithProviders(<GlassPanel>Chat</GlassPanel>)
    const panel = await screen.findByText('Chat')
    fireEvent.pointerMove(panel, { clientX: 40, clientY: 30 })
    expect(panel.style.getPropertyValue('--mx')).toBe('')
  })
})
