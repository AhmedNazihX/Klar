import { describe, expect, it } from 'vitest'

import { hasPassed, passedCount, TIMELINE_DATES, todayPosition } from './timeline'

const DATES = TIMELINE_DATES.map(({ isoDate }) => isoDate)

/** A local calendar day, as the visitor's clock gives it. */
function day(year: number, month: number, date: number): Date {
  return new Date(year, month - 1, date, 15, 30)
}

describe('the timeline dates', () => {
  it('are the amended application dates, in order', () => {
    expect(DATES).toEqual(['2026-08-02', '2026-12-02', '2027-12-02', '2028-08-02'])
  })
})

describe('todayPosition', () => {
  it('sits on a date on that day', () => {
    expect(todayPosition(DATES, day(2026, 8, 2))).toBe(0)
    expect(todayPosition(DATES, day(2027, 12, 2))).toBe(2)
  })

  it('places a day between two dates by the days elapsed', () => {
    // 10 October 2026: 69 of the 122 days from 2 August to 2 December.
    expect(todayPosition(DATES, day(2026, 10, 10))).toBeCloseTo(69 / 122, 6)
  })

  it('stays on the line before the first date and after the last', () => {
    expect(todayPosition(DATES, day(2026, 1, 1))).toBe(0)
    expect(todayPosition(DATES, day(2030, 1, 1))).toBe(3)
  })
})

describe('hasPassed and passedCount', () => {
  it('counts a date as passed from its own day', () => {
    expect(hasPassed('2026-12-02', day(2026, 12, 1))).toBe(false)
    expect(hasPassed('2026-12-02', day(2026, 12, 2))).toBe(true)
  })

  it('counts the dates that apply already', () => {
    expect(passedCount(DATES, day(2026, 7, 1))).toBe(0)
    expect(passedCount(DATES, day(2026, 10, 10))).toBe(1)
    expect(passedCount(DATES, day(2028, 8, 2))).toBe(4)
  })
})
