import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

// Read from disk: Vitest does not load CSS, not even with `?raw`. Vitest runs from frontend/.
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8')

// The design system's own token file (docs/design-system/tokens.json), the source of the values.
type Token = { name: string; value: string }
type TypeStyle = {
  name: string
  fontSize: string
  lineHeight: number
  fontWeight: number
  letterSpacing?: string
}
type Tokens = {
  color: { tokens: Token[] }
  radius: { tokens: Token[] }
  motion: { tokens: Token[] }
  shadow: { tokens: Token[] }
  spacing: { tokens: Token[] }
  backdrop: { tokens: Token[] }
  type: { groups: { styles: TypeStyle[] }[] }
}
const tokens = JSON.parse(
  readFileSync(resolve(process.cwd(), '../docs/design-system/tokens.json'), 'utf-8'),
) as Tokens

/** The value of a custom property in index.css, or undefined. */
function cssVar(name: string): string | undefined {
  return new RegExp(`${name}:\\s*([^;]+);`).exec(css)?.[1]
}

/** Spacing and number spelling normalised, so Prettier's `0.4` equals the system's `0.40`. */
function normalise(value: string): string {
  return value
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/\s*([(),])\s*/g, '$1')
    .replace(/-?\d*\.?\d+/g, (number) => String(Number(number)))
    .trim()
}

function expectToken(cssName: string, value: string): void {
  const actual = cssVar(cssName)
  expect(actual, `${cssName} is missing from index.css`).toBeDefined()
  expect(normalise(actual ?? '')).toBe(normalise(value))
}

describe('index.css agrees with docs/design-system/tokens.json', () => {
  it.each(tokens.color.tokens.map((t) => [t.name, t.value]))('colour %s', (name, value) => {
    expectToken(`--color-${name}`, value)
  })

  it.each(tokens.radius.tokens.map((t) => [t.name, t.value]))('radius %s', (name, value) => {
    expectToken(`--${name}`, value)
  })

  it.each(tokens.motion.tokens.map((t) => [t.name, t.value]))('motion %s', (name, value) => {
    expectToken(`--${name}`, value)
  })

  it.each(
    [...tokens.shadow.tokens, ...tokens.spacing.tokens, ...tokens.backdrop.tokens].map((t) => [
      t.name,
      t.value,
    ]),
  )('shadow, spacing and backdrop %s', (name, value) => {
    expectToken(`--${name}`, value)
  })

  it.each(tokens.type.groups.flatMap((group) => group.styles).map((style) => [style.name, style]))(
    'type style %s',
    (name, style) => {
      expectToken(`--text-${name}`, style.fontSize)
      expectToken(`--text-${name}--line-height`, String(style.lineHeight))
      expectToken(`--text-${name}--font-weight`, String(style.fontWeight))
      if (style.letterSpacing) expectToken(`--text-${name}--letter-spacing`, style.letterSpacing)
    },
  )

  it('has every motion token the story names', () => {
    for (const name of [
      'ease-settle',
      'ease-out',
      'duration-hover',
      'duration-reveal',
      'duration-exit',
      'stagger',
      'focus-blur',
      'glint',
    ]) {
      expect(cssVar(`--${name}`), name).toBeDefined()
    }
    expect(normalise(cssVar('--duration-hover') ?? '')).toBe('350ms')
    expect(normalise(cssVar('--duration-reveal') ?? '')).toBe('900ms')
    expect(normalise(cssVar('--duration-exit') ?? '')).toBe('500ms')
    expect(normalise(cssVar('--stagger') ?? '')).toBe('110ms')
  })
})

describe('theme', () => {
  it('uses Geist for the product, Newsreader for the Act and Lexend for the verdict', () => {
    expect(cssVar('--font-sans')).toMatch(/^'Geist Variable'/)
    expect(cssVar('--font-serif')).toMatch(/^'Newsreader Variable'/)
    expect(cssVar('--font-brand')).toMatch(/^'Lexend'/)
  })

  it('self-hosts Lexend 500 and 600 through fontsource', () => {
    expect(css).toContain("@import '@fontsource/lexend/500.css';")
    expect(css).toContain("@import '@fontsource/lexend/600.css';")
  })

  it('builds glass from the tokens: glass-top to glass-bottom at 150°, blur-glass, saturate-glass', () => {
    const glass = /@utility glass \{([^}]+)\}/.exec(css)?.[1] ?? ''
    expect(glass).toContain(
      'linear-gradient(150deg, var(--color-glass-top), var(--color-glass-bottom))',
    )
    expect(glass).toContain('blur(var(--blur-glass)) saturate(var(--saturate-glass))')
    expect(glass).toContain('box-shadow: var(--shadow-glass)')
  })

  it('lays the four mesh lights on the mist ground', () => {
    const ground = /@utility bg-ground \{([^}]+)\}/.exec(css)?.[1] ?? ''
    for (const light of ['mesh-blue', 'mesh-peach', 'mesh-teal', 'mesh-lilac']) {
      expect(ground).toContain(`var(--color-${light}), transparent 62%`)
    }
  })

  it('turns every animation and transition off for reduced motion', () => {
    const block =
      /\/\* reduced-motion:start[\s\S]*?\*\/([\s\S]*?)\/\* reduced-motion:end \*\//.exec(
        css,
      )?.[1] ?? ''
    expect(block).toContain('@media (prefers-reduced-motion: reduce)')
    expect(block).toMatch(
      /\*,\s*::before,\s*::after\s*\{[^}]*animation: none !important;[^}]*transition: none !important;/,
    )
    // .lift moves with `transform`, which this block can reset; the button's translate and scale
    // are motion-safe only (build.test.ts checks the compiled CSS).
    expect(block).toMatch(/\.lift:hover\s*\{\s*transform: none !important;/)
    expect(block).not.toContain('klar-button')
    expect(block).toMatch(/\.glint::after\s*\{\s*display: none;/)
  })
})
