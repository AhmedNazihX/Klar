import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { extname, join, resolve } from 'node:path'

import { render, screen } from '@testing-library/react'
import postcss, { type AtRule, type Container, type Document, type Rule } from 'postcss'
import { createElement } from 'react'
import { build } from 'vite'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

import { Button } from './components/Button'

// Builds the app the way `pnpm build` does, into a temporary folder, and reads what would ship.
// It runs in the default jsdom environment only because the shared test set-up needs a document.
const BUILD_TIMEOUT_MS = 120_000
const TEXT_FILES = new Set(['.html', '.css', '.js', '.json', '.svg', '.webmanifest'])
const GOOGLE_FONTS = /fonts\.(googleapis|gstatic)\.com/

let outDir = ''
let files: string[] = []

beforeAll(async () => {
  outDir = mkdtempSync(join(tmpdir(), 'klar-build-'))
  await build({
    configFile: resolve(process.cwd(), 'vite.config.ts'),
    logLevel: 'silent',
    build: { outDir, emptyOutDir: true },
  })
  files = readdirSync(outDir, { recursive: true, encoding: 'utf-8' })
}, BUILD_TIMEOUT_MS)

afterAll(() => {
  if (outDir) rmSync(outDir, { recursive: true, force: true })
})

describe('the built app', () => {
  it('loads nothing from Google Fonts (decision 026, C2)', () => {
    const shipped = files.filter((file) => TEXT_FILES.has(extname(file)))
    expect(shipped.length).toBeGreaterThan(0)
    for (const file of shipped) {
      expect(readFileSync(join(outDir, file), 'utf-8'), file).not.toMatch(GOOGLE_FONTS)
    }
  })

  it('self-hosts the three faces: Geist, Newsreader and Lexend', () => {
    const fonts = files.filter((file) => file.endsWith('.woff2'))
    for (const family of ['geist', 'newsreader', 'lexend']) {
      expect(
        fonts.some((file) => file.toLowerCase().includes(family)),
        family,
      ).toBe(true)
    }
  })

  it('moves the button on hover and press only when motion is allowed', () => {
    render(createElement(Button, null, 'Classify a tool'))
    const motion = screen
      .getByRole('button', { name: 'Classify a tool' })
      .className.split(' ')
      .filter((name) => /translate|scale/.test(name) && !name.startsWith('transition'))
    expect(motion.length).toBeGreaterThan(0)

    const root = postcss.parse(
      files
        .filter((file) => file.endsWith('.css'))
        .map((file) => readFileSync(join(outDir, file), 'utf-8'))
        .join('\n'),
    )
    for (const name of motion) {
      expect(name, name).toMatch(/^motion-safe:/)
      const selector = `.${name.replace(/[^a-zA-Z0-9_-]/g, (c) => `\\${c}`)}`
      const rules: Rule[] = []
      root.walkRules((rule) => {
        if (rule.selectors.some((part) => part.includes(selector))) rules.push(rule)
      })
      expect(rules.length, `${name} is in the built CSS`).toBeGreaterThan(0)
      for (const rule of rules) {
        expect(enclosingAtRules(rule), name).toContain(
          '@media (prefers-reduced-motion:no-preference)',
        )
      }
    }
  })
})

/** The at-rules (`@media …`) that enclose a rule, innermost first, as postcss parsed them. */
function enclosingAtRules(rule: Rule): string[] {
  const atRules: string[] = []
  for (let node: Container | Document | undefined = rule.parent; node; node = node.parent) {
    if (node.type === 'atrule') {
      const atRule = node as AtRule
      atRules.push(`@${atRule.name} ${atRule.params}`)
    }
  }
  return atRules
}
