import { describe, expect, it } from 'vitest'

import de from './locales/de.json'
import en from './locales/en.json'

// Every key path to a string, e.g. "pill.high_risk".
function leafKeys(tree: object, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]: [string, unknown]) =>
    typeof value === 'object' && value !== null
      ? leafKeys(value, `${prefix}${key}.`)
      : [`${prefix}${key}`],
  )
}

function leafValues(tree: object): unknown[] {
  return Object.values(tree).flatMap((value: unknown) =>
    typeof value === 'object' && value !== null ? leafValues(value) : [value],
  )
}

/** Key path to string, e.g. { "pill.high_risk": "High-risk" }. */
function flatten(tree: object, prefix = ''): Map<string, string> {
  return new Map(
    Object.entries(tree).flatMap(([key, value]: [string, unknown]): [string, string][] =>
      typeof value === 'object' && value !== null
        ? [...flatten(value, `${prefix}${key}.`)]
        : [[`${prefix}${key}`, String(value)]],
    ),
  )
}

const EN = flatten(en)
const DE = flatten(de)

/** The {{name}} placeholders and <tag/> components a string carries, sorted. */
function slots(text: string): string[] {
  const placeholders = [...text.matchAll(/\{\{\s*([\w.]+)[^}]*\}\}/g)].map((m) => `{{${m[1]}}}`)
  const components = [...text.matchAll(/<(\w+)\s*\/?>/g)].map((m) => `<${m[1]}>`)
  return [...placeholders, ...components].sort()
}

/**
 * German strings that are the same as the English on purpose: names, numbers, citations that
 * read alike, the Impressum (German on both sites, as German law asks), and loanwords German uses
 * as they are. Anything else identical is an untranslated string (P11). Add to this list only
 * after checking the German.
 */
const SAME_IN_BOTH = new Set([
  'app.name',
  'ask.klar',
  'language.en',
  'language.de',
  'brand.swatch.mist',
  'brand.swatch.ink',
  'brand.swatch.slate',
  'brand.swatch.lens',
  'site.footer.impressum',
  'site.page.impressum',
  'sitePages.method.limits.labels',
  'sitePages.contact.write.feedback',
  'documents.interview.sectionTitle',
  'yourData.who.searchRole',
  'yourData.who.storageRole',
  'inventory.table.tool',
  'inventory.table.status',
  'inventory.table.none',
  'diff.noValue',
  'diff.steps.withPoint',
  'progress.detail',
  'result.question.ifYesPointNoDate',
  'result.citationSource',
  'prohibited.pointLine',
  'followUp.answerLine',
  'landing.accuracy.pending',
])
const SAME_PREFIXES = [
  'sitePages.impressum.body.',
  'welcome.staffBand.',
  'progress.reference.',
  'landing.hero.checks.',
  'landing.how.checks.',
]

function isSameOnPurpose(key: string): boolean {
  return SAME_IN_BOTH.has(key) || SAME_PREFIXES.some((prefix) => key.startsWith(prefix))
}

// The app's source files (tests, generated code and fixtures left out), as text.
const SOURCES = Object.entries(
  import.meta.glob<string>(['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}', '!../test/**'], {
    query: '?raw',
    import: 'default',
    eager: true,
  }),
).filter(([path]) => !path.endsWith('.gen.ts') && !path.includes('/api/'))

/** The keys the code passes to t() as a literal, and the fixed prefixes of the template ones. */
function keysInCode(): { literal: [string, string][]; prefixes: [string, string][] } {
  const literal: [string, string][] = []
  const prefixes: [string, string][] = []
  const call = /\b(?:t|i18n\.t)\(\s*(['"`])([^'"`]+)\1/g
  const trans = /i18nKey=\{?(['"`])([^'"`]+)\1/g
  for (const [path, text] of SOURCES) {
    for (const match of [...text.matchAll(call), ...text.matchAll(trans)]) {
      const key = match[2] ?? ''
      if (!key.includes('${')) literal.push([path, key])
      else if (!key.startsWith('${')) prefixes.push([path, key.slice(0, key.indexOf('${'))])
    }
  }
  return { literal, prefixes }
}

function hasKey(key: string): boolean {
  return EN.has(key) || EN.has(`${key}_one`) || EN.has(`${key}_other`)
}

describe('locales', () => {
  it('have the same keys in English and German', () => {
    expect(leafKeys(de).sort()).toEqual(leafKeys(en).sort())
  })

  it.each([
    ['en', en],
    ['de', de],
  ])('%s has no empty strings', (_, resources) => {
    for (const value of leafValues(resources)) {
      expect(typeof value === 'string' && value.trim().length > 0).toBe(true)
    }
  })

  it('give every German string the same placeholders and components as the English', () => {
    const differing = [...EN].filter(
      ([key, text]) => slots(text).join() !== slots(DE.get(key) ?? '').join(),
    )
    expect(differing.map(([key]) => key)).toEqual([])
  })

  it('translate every string, except the ones listed as the same on purpose', () => {
    const untranslated = [...EN]
      .filter(([key, text]) => DE.get(key) === text && !isSameOnPurpose(key))
      .map(([key]) => key)
    expect(untranslated).toEqual([])
  })

  it('list as the same on purpose only keys that exist and still read the same', () => {
    const stale = [...SAME_IN_BOTH].filter((key) => !EN.has(key) || EN.get(key) !== DE.get(key))
    expect(stale).toEqual([])
  })

  it('cite in the German style in German (Art. 26 Abs. 1, Anhang III), never the English', () => {
    const english = [...DE]
      .filter(([, text]) => /Art\.\s*\d+[a-z]?\(|\bAnnex\b|\bpoint \d/.test(text))
      .map(([key]) => key)
    expect(english).toEqual([])
  })

  it('address the reader as Sie in German, never du', () => {
    const informal = [...DE]
      .filter(([, text]) => /\b(du|dich|dir|dein|deine|deinen|deiner)\b/i.test(text))
      .map(([key]) => key)
    expect(informal).toEqual([])
  })
})

describe('key coverage', () => {
  const { literal, prefixes } = keysInCode()

  it('reads the source files', () => {
    expect(SOURCES.length).toBeGreaterThan(100)
    expect(literal.length).toBeGreaterThan(500)
    expect(prefixes.length).toBeGreaterThan(50)
  })

  it('finds every key the code asks for in the locales', () => {
    const missing = literal.filter(([, key]) => !hasKey(key))
    expect(missing).toEqual([])
  })

  it('finds a group of keys under every key the code builds from a variable', () => {
    const missing = prefixes.filter(
      ([, prefix]) => ![...EN.keys()].some((key) => key.startsWith(prefix)),
    )
    expect(missing).toEqual([])
  })

  it('shows no fixed English text in the components (JSX text and labels go through t())', () => {
    const text = /(?<![=-])>\s*[A-Za-z][A-Za-z ,.'!?-]{2,}\s*</ // not an arrow's =>
    const label = /(?<![\w-])(aria-label|placeholder|title|alt)="[A-Za-z][^"]{2,}"/
    const hardCoded = SOURCES.filter(
      ([path]) => path.endsWith('.tsx') && !path.includes('/ui/'),
    ).flatMap(([path, source]) =>
      source
        .split('\n')
        .filter((line) => !line.trim().startsWith('//'))
        .filter((line) => text.test(line) || label.test(line))
        .map((line) => `${path}: ${line.trim()}`),
    )
    expect(hardCoded).toEqual([])
  })
})
