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
})
