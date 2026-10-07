import { describe, expect, it } from 'vitest'

import { formatBytes } from './user-data'

describe('formatBytes', () => {
  it.each([
    [0, 'en', '0 kB'],
    [1, 'en', '< 1 kB'],
    [511, 'en', '< 1 kB'],
    [1023, 'en', '< 1 kB'],
    [1024, 'en', '1 kB'],
    [12 * 1024, 'en', '12 kB'],
    [1.5 * 1024 * 1024, 'en', '1.5 MB'],
    [0, 'de', '0 kB'],
    [511, 'de', '< 1 kB'],
    [12 * 1024, 'de', '12 kB'],
    [1.5 * 1024 * 1024, 'de', '1,5 MB'],
  ])('shows %i bytes in %s as %s', (bytes, language, shown) => {
    expect(formatBytes(bytes, language)).toBe(shown)
  })
})
