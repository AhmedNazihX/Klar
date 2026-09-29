import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

// Read from disk: Vitest does not load CSS, not even with `?raw`. Vitest runs from frontend/.
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8')

// The Brand board's values (Design canvas, project/Brand.dc.html), copied by hand. When the board
// changes, update this table and src/index.css together.
const BRAND_BOARD = {
  '--color-mist': '#e6ecf3',
  '--color-ink': '#0f1b2d',
  '--color-slate': '#4a5670',
  '--color-lens': '#2d4be0',
  '--color-risk-prohibited': '#9b1c1c',
  '--color-risk-prohibited-dot': '#d93a3a',
  '--color-risk-high': '#873a00',
  '--color-risk-high-dot': '#e57a1e',
  '--color-risk-limited': '#16498a',
  '--color-risk-limited-dot': '#3b82d6',
  '--color-risk-minimal': '#1d5a39',
  '--color-risk-minimal-dot': '#3a9a64',
  '--color-risk-out': '#465066',
  '--color-risk-out-dot': '#8a93a6',
  '--color-status-ambiguous': '#55289a',
  '--color-status-info': '#0f1b2d',
} as const

function token(name: string): string | undefined {
  const escaped = name.replace(/[-]/g, '\\-')
  return new RegExp(`${escaped}:\\s*([^;]+);`).exec(css)?.[1]?.trim()
}

describe('theme tokens', () => {
  it.each(Object.entries(BRAND_BOARD))('%s matches the Brand board', (name, value) => {
    expect(token(name)).toBe(value)
  })

  it('uses Geist for the product and Newsreader for the Act', () => {
    expect(token('--font-sans')).toMatch(/^'Geist Variable'/)
    expect(token('--font-serif')).toMatch(/^'Newsreader Variable'/)
  })

  it('follows the glass recipe: 68% to 30% at 150°, blur 26 px, saturation 175%', () => {
    const glass = /@utility glass \{([^}]+)\}/.exec(css)?.[1] ?? ''
    expect(glass).toContain(
      'linear-gradient(150deg, rgb(255 255 255 / 0.68), rgb(255 255 255 / 0.3))',
    )
    expect(glass).toContain('blur(26px) saturate(175%)')
    expect(glass).toContain('1px solid rgb(255 255 255 / 0.8)')
    expect(glass).toContain('0 22px 50px -20px rgb(28 44 86 / 0.3)')
  })
})
