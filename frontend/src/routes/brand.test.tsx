import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import { renderRoute } from '@/test/test-utils'

describe('/brand', () => {
  it('shows the palette, all seven pills and the three voices', async () => {
    renderRoute('/brand')

    expect(await screen.findByRole('heading', { name: 'Brand tokens' })).toBeInTheDocument()
    for (const name of ['Mist', 'Ink', 'Slate', 'Lens blue']) {
      expect(screen.getByText(name)).toBeInTheDocument()
    }
    expect(
      screen.getAllByRole('listitem').filter((item) => item.querySelector('[data-kind]')),
    ).toHaveLength(7)
    expect(screen.getByRole('heading', { name: 'Three voices' })).toBeInTheDocument()
    expect(screen.getByText('The product speaks in Geist.')).not.toHaveClass(
      'font-serif',
      'font-brand',
    )
    expect(screen.getByText(/The Act speaks in Newsreader/)).toHaveClass('font-serif')
    // The verdict is Klar's, in Lexend at the verdict size.
    expect(screen.getByText('High-risk', { selector: 'p' })).toHaveClass(
      'font-brand',
      'text-verdict',
    )
  })

  it('shows the base components', async () => {
    renderRoute('/brand')
    await screen.findByRole('heading', { name: 'Brand tokens' })

    expect(screen.getByRole('button', { name: 'Classify a tool' })).toHaveClass('liquid-primary')
    expect(screen.getByRole('group', { name: 'View' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Law version' })).toBeInTheDocument()
    expect(screen.getByText('DRAFT')).toBeInTheDocument()
    expect(screen.getByText('Assumed')).toBeInTheDocument()
    expect(
      screen.getByText('Guidance, not legal advice. Klar is an AI system.'),
    ).toBeInTheDocument()
    expect(screen.getByText('2 December 2027')).toBeInTheDocument()
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = renderRoute('/brand')
    await screen.findByRole('heading', { name: 'Brand tokens' })
    // jsdom cannot paint, so colour contrast is checked in the browser (P13) and, for the primary
    // button, against the tokens in Button.test.tsx.
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})
