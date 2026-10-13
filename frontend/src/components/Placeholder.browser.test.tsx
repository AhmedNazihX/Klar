// A placeholder's contrast in a real browser (P31, from P17's and P26's reviews): its Lens blue
// text keeps WCAG AA (4.5:1) on its own tint wherever it sits, the strongest mesh light (blue, at
// its 0.55 peak) behind it included, because the tint is opaque.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Placeholder } from './Placeholder'

const AA_TEXT = 4.5

type Rgba = [number, number, number, number]

function rgba(css: string): Rgba {
  const parts = css.match(/[\d.]+/g)?.map(Number) ?? []
  const [red = 0, green = 0, blue = 0, alpha = 1] = parts
  return [red, green, blue, alpha]
}

function luminance([red, green, blue]: Rgba): number {
  const channel = (value: number): number => {
    const share = value / 255
    return share <= 0.03928 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)
}

function contrast(first: Rgba, second: Rgba): number {
  const [lighter, darker] = [luminance(first), luminance(second)].sort((a, b) => b - a)
  return ((lighter ?? 0) + 0.05) / ((darker ?? 0) + 0.05)
}

describe('Placeholder', () => {
  it('keeps AA contrast over the blue mesh light', () => {
    render(
      <div style={{ background: 'var(--color-mesh-blue)' }}>
        <Placeholder>[NAME]</Placeholder>
      </div>,
    )
    const style = getComputedStyle(screen.getByText('[NAME]'))
    const tint = rgba(style.backgroundColor)
    // Opaque: what is behind it doesn't show through.
    expect(tint[3]).toBe(1)
    expect(contrast(rgba(style.color), tint)).toBeGreaterThanOrEqual(AA_TEXT)
  })
})
