import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { extname, join, resolve } from 'node:path'

import { build } from 'vite'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

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
})
