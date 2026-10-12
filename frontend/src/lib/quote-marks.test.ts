import { describe, expect, it } from 'vitest'

import { nestQuotes } from './quote-marks'

describe('nestQuotes', () => {
  it.each([
    ['de', '„Betreiber“ eine natürliche Person;', '‚Betreiber‘ eine natürliche Person;'],
    ['de', 'gilt als „Betreiber“', 'gilt als ‚Betreiber‘'],
    ['en', '“deployer” means a person', '‘deployer’ means a person'],
    ['en', 'the provider’s instructions', 'the provider’s instructions'],
    ['de', 'ohne Anführungszeichen', 'ohne Anführungszeichen'],
  ] as const)('nests the %s marks of %s', (language, text, nested) => {
    expect(nestQuotes(text, language)).toBe(nested)
  })
})
