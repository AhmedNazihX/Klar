import { readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { Icon } from './Icon'
import { ICON_FILES, ICON_NAMES } from './icon-files'

const ICON_DIR = resolve(process.cwd(), 'src/components/icons')

// The design system's Icons asset group (docs/design-system/components.md › Assets › Icons).
const SYSTEM_ICONS = [
  'inventory',
  'classify',
  'obligations',
  'documents',
  'ask',
  'add',
  'privacy',
  'check',
  'info',
  'alert',
  'chevron-down',
  'send',
]

describe('Icon', () => {
  it('has the system’s twelve icons, each copied as a file', () => {
    expect([...ICON_NAMES].sort()).toEqual([...SYSTEM_ICONS].sort())
    const files = readdirSync(ICON_DIR).sort()
    expect(files).toEqual(SYSTEM_ICONS.map((name) => `${name}.svg`).sort())
    for (const file of files) {
      const svg = readFileSync(resolve(ICON_DIR, file), 'utf-8')
      // The line set: 24 px grid, no fills, round caps or joins, drawn in ink.
      expect(svg, file).toMatch(
        /^<svg [^>]*viewBox="0 0 24 24"[^>]*fill="none"[^>]*stroke="#0F1B2D"/,
      )
      expect(svg, file).toMatch(/stroke-line(cap|join)="round"/)
      expect(svg, file).not.toMatch(/<script|on[a-z]+=/i)
    }
  })

  it('is decorative unless given a title', async () => {
    renderWithProviders(
      <p>
        <Icon name="inventory" />
        Inventory
      </p>,
    )
    const label = await screen.findByText('Inventory')
    const icon = label.querySelector('[data-icon="inventory"]')
    expect(icon).toHaveAttribute('aria-hidden', 'true')
    expect(icon).not.toHaveAttribute('role')
  })

  it('carries a name when it stands alone with a title, and paints its file in currentColor', async () => {
    renderWithProviders(<Icon name="send" title="Ask" size={20} />)
    const icon = await screen.findByRole('img', { name: 'Ask' })
    expect(icon).toHaveClass('bg-current')
    expect(icon.style.width).toBe('20px')
    expect(icon.getAttribute('style')).toContain(`mask: url("${ICON_FILES.send}")`)
  })
})
