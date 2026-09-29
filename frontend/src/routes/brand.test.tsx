import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import { renderRoute } from '@/test/test-utils'

describe('/brand', () => {
  it('shows the palette, all seven pills and both voices', async () => {
    renderRoute('/brand')

    expect(await screen.findByRole('heading', { name: 'Brand tokens' })).toBeInTheDocument()
    for (const name of ['Mist', 'Ink', 'Slate', 'Lens blue']) {
      expect(screen.getByText(name)).toBeInTheDocument()
    }
    expect(
      screen.getAllByRole('listitem').filter((item) => item.querySelector('[data-kind]')),
    ).toHaveLength(7)
    expect(screen.getByText(/The Act speaks in Newsreader/)).toHaveClass('font-serif')
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = renderRoute('/brand')
    await screen.findByRole('heading', { name: 'Brand tokens' })
    // jsdom cannot paint, so colour contrast is checked in the browser (P13), not here.
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    expect(results.violations).toEqual([])
  })
})
