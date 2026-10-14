import { describe, expect, it } from 'vitest'

import { isRelieved, reliefNote } from './relief'

describe('isRelieved', () => {
  it.each([
    ['sme', 'amended', true],
    ['smc', 'amended', true],
    ['sme', 'original', false],
    ['smc', 'original', false],
    ['none', 'amended', false],
    [null, 'amended', false],
    [undefined, 'amended', false],
  ] as const)('size %s under the %s text: %s', (sizeClass, shown, expected) => {
    expect(isRelieved(sizeClass, shown)).toBe(expected)
  })
})

describe('reliefNote', () => {
  const BOTH = { relief_note: 'Lighter.', relief_note_de: 'Leichter.' }

  it('reads the note in the language shown', () => {
    expect(reliefNote(BOTH, 'en')).toBe('Lighter.')
    expect(reliefNote(BOTH, 'de')).toBe('Leichter.')
  })

  it("never shows the other language's note in place of a missing one", () => {
    expect(reliefNote({ relief_note: 'Lighter.' }, 'de')).toBeNull()
    expect(reliefNote({ relief_note: null, relief_note_de: 'Leichter.' }, 'en')).toBeNull()
  })

  it('is null for a duty the table gives no note', () => {
    expect(reliefNote(undefined, 'en')).toBeNull()
    expect(reliefNote({ relief_note: null, relief_note_de: null }, 'de')).toBeNull()
  })
})
