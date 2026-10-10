import { describe, expect, it } from 'vitest'

import { monthsSince, routeDates } from './dates'

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

describe('monthsSince', () => {
  it.each([
    ['2025-02-02', '2026-10-01', 20],
    ['2025-02-02', '2025-03-02', 1],
    ['2025-02-02', '2025-02-16', 0],
    ['2025-02-02', '2025-02-02', 0],
    ['2026-12-02', '2026-10-01', 0],
  ])('counts the months from %s to %s as %i', (date, today, count) => {
    expect(monthsSince(date, new Date(`${today}T12:00:00`))).toBe(count)
  })
})
