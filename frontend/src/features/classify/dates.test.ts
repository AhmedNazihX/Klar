import { describe, expect, it } from 'vitest'

import { routeDates } from './dates'

describe('routeDates', () => {
  it.each([
    ['annex_iii', '2027-12-02', '2026-08-02'],
    ['annex_i', '2028-08-02', '2027-08-02'],
  ] as const)('gives the %s route its original Art. 113 date', (route, amended, original) => {
    expect(routeDates(route, amended)).toEqual({ amended, original })
  })

  it('keeps the date under both texts without a route', () => {
    expect(routeDates(null, '2026-08-02')).toEqual({
      amended: '2026-08-02',
      original: '2026-08-02',
    })
  })
})
