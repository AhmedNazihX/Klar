import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { extname, join, resolve } from 'node:path'

import { render, screen } from '@testing-library/react'
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

    const css = files
      .filter((file) => file.endsWith('.css'))
      .map((file) => readFileSync(join(outDir, file), 'utf-8'))
      .join('\n')
    for (const name of motion) {
      expect(name, name).toMatch(/^motion-safe:/)
      const selector = `.${name.replace(/[^a-zA-Z0-9_-]/g, (c) => `\\${c}`)}`
      let at = css.indexOf(selector)
      expect(at, `${name} is in the built CSS`).toBeGreaterThanOrEqual(0)
      while (at >= 0) {
        expect(enclosingAtRules(css, at), name).toContain(
          '@media (prefers-reduced-motion:no-preference)',
        )
        at = css.indexOf(selector, at + selector.length)
      }
    }
  })
})

/** The at-rule preludes (`@media …`) of the blocks that enclose position `at` in minified CSS. */
function enclosingAtRules(css: string, at: number): string[] {
  const stack: string[] = []
  let start = 0
  for (let i = 0; i < at; i += 1) {
    const c = css[i]
    if (c === '{') {
      stack.push(css.slice(start, i).trim())
      start = i + 1
    } else if (c === '}') {
      stack.pop()
      start = i + 1
    } else if (c === ';') {
      start = i + 1
    }
  }
  return stack.filter((prelude) => prelude.startsWith('@'))
}
