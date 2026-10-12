import { afterEach, describe, expect, it, vi } from 'vitest'

import { formatBytes } from './user-data'

afterEach(() => {
  vi.restoreAllMocks()
})

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
    [1234.5 * 1024 * 1024, 'en', '1,234.5 MB'],
    [1234.5 * 1024 * 1024, 'de', '1.234,5 MB'],
  ] as const)('shows %i bytes in %s as %s', (bytes, language, shown) => {
    expect(formatBytes(bytes, language)).toBe(shown)
  })

  it.each([
    ['en', 'en-GB'],
    ['de', 'de-DE'],
  ] as const)('formats %s in the %s locale, like dates and lists', (language, locale) => {
    const numberFormat = vi.spyOn(Intl, 'NumberFormat')
    formatBytes(12 * 1024, language)
    expect(numberFormat).toHaveBeenCalledWith(locale, expect.anything())
  })
})
