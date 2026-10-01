import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/test-utils'

import { Button } from './Button'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8')
const tokens = JSON.parse(
  readFileSync(resolve(process.cwd(), '../docs/design-system/tokens.json'), 'utf-8'),
) as { color: { tokens: { name: string; value: string }[] } }

function tokenHex(name: string): string {
  const value = tokens.color.tokens.find((token) => token.name === name)?.value
  if (!value?.startsWith('#')) throw new Error(`${name} is not a hex colour in tokens.json`)
  return value
}

type Rgb = readonly [number, number, number]

function rgb(hex: string): Rgb {
  const n = Number.parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

// WCAG 2.2 relative luminance and contrast ratio.
function luminance([r, g, b]: Rgb): number {
  const [lr, lg, lb] = [r, g, b].map((channel) => {
    const c = channel / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]
  return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb
}

function contrast(a: Rgb, b: Rgb): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (light + 0.05) / (dark + 0.05)
}

type Stop = { colour: Rgb; at: number }

/** The primary button's gradient stops, read from the liquid-primary utility in index.css. */
function primaryStops(): Stop[] {
  const utility =
    /@utility liquid-primary \{[\s\S]*?linear-gradient\(([\s\S]*?)\);/.exec(css)?.[1] ?? ''
  return [...utility.matchAll(/var\(--color-([a-z-]+)\)\s+(\d+)%/g)].map(([, name, at]) => ({
    colour: rgb(tokenHex(name ?? '')),
    at: Number(at),
  }))
}

function colourAt(stops: Stop[], at: number): Rgb {
  const upper = stops.findIndex((stop) => stop.at >= at)
  const high = stops[upper]
  const low = stops[Math.max(upper - 1, 0)]
  if (!high || !low) throw new Error(`no gradient stop at ${at}%`)
  const t = high.at === low.at ? 0 : (at - low.at) / (high.at - low.at)
  return low.colour.map((c, i) => c + ((high.colour[i] ?? c) - c) * t) as unknown as Rgb
}

// The label's glyphs sit in the middle half of the button's height at every size.
const LABEL_BAND: { from: number; to: number } = { from: 25, to: 75 }
const WHITE: Rgb = [255, 255, 255]

describe('Button', () => {
  it('renders the primary button with the liquid Lens blue and runs its action', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    renderWithProviders(<Button onClick={onClick}>Classify a tool</Button>)

    const button = await screen.findByRole('button', { name: 'Classify a tool' })
    expect(button).toHaveAttribute('type', 'button')
    expect(button).toHaveClass('liquid-primary', 'shadow-button', 'rounded-pill', 'shrink-0')
    await user.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('renders the ghost button as glass, with a decorative leading icon', async () => {
    renderWithProviders(
      <Button variant="ghost" size="sm" icon="add">
        Add a tool
      </Button>,
    )
    const button = await screen.findByRole('button', { name: 'Add a tool' })
    expect(button).toHaveClass('shadow-button-ghost', 'h-[34px]')
    expect(button).not.toHaveClass('liquid-primary')
    expect(button.querySelector('[data-icon="add"]')).toHaveAttribute('aria-hidden', 'true')
  })

  it('does nothing while disabled', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    renderWithProviders(
      <Button disabled onClick={onClick}>
        Draft documents
      </Button>,
    )
    await user.click(await screen.findByRole('button', { name: 'Draft documents' }))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('keeps white label text at 4.5:1 or more over the gradient behind it', async () => {
    // The check below assumes white: tie it to the label colour the primary button really uses.
    renderWithProviders(<Button>Classify a tool</Button>)
    const button = await screen.findByRole('button', { name: 'Classify a tool' })
    expect(button).toHaveClass('text-white')
    expect(button.className.split(' ').filter((name) => /^text-(?!\[)/.test(name))).toEqual([
      'text-white',
    ])

    const stops = primaryStops()
    expect(stops.map((stop) => stop.at)).toEqual([0, 55, 100])
    // White on lens-blue itself, the colour the label sits over.
    expect(contrast(WHITE, rgb(tokenHex('lens-blue')))).toBeGreaterThanOrEqual(4.5)
    for (let at = LABEL_BAND.from; at <= LABEL_BAND.to; at += 1) {
      expect(contrast(WHITE, colourAt(stops, at)), `at ${at}%`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('needs the band: the top stop alone would fail', () => {
    expect(contrast(WHITE, rgb(tokenHex('lens-blue-top')))).toBeLessThan(4.5)
  })
})
