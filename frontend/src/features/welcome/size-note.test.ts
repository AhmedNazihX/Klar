import { describe, expect, it } from 'vitest'

import { describeSize } from './size-note'

describe('describeSize under the amended text', () => {
  it.each([
    ['10-49', 'up_to_10m', 'sme', [], ['art99_3', 'art99_6']],
    ['50-249', 'up_to_150m', 'smc', ['maybeSme'], ['art99_3', 'art99_6a']],
    ['250-749', 'up_to_50m', 'smc', [], ['art99_3', 'art99_6a']],
    ['1-9', 'over_150m', 'none', ['maybeSme', 'maybeSmc'], ['art99_3', 'art99_6', 'art99_6a']],
    ['250-749', 'over_150m', 'none', ['maybeSmc'], ['art99_3', 'art99_6', 'art99_6a']],
    ['750+', 'up_to_10m', 'none', [], ['art99_3', 'art99_6', 'art99_6a']],
  ] as const)('%s staff, %s: %s', (staff, turnover, line, caveats, quotes) => {
    expect(describeSize(staff, turnover, 'amended')).toEqual({ line, caveats, quotes })
  })
})

describe('describeSize under the original 2024 text (no small mid-caps)', () => {
  it.each([
    ['10-49', 'up_to_10m', 'sme', []],
    ['50-249', 'up_to_150m', 'noneOriginal', ['maybeSme']],
    ['250-749', 'up_to_50m', 'noneOriginal', []],
    ['250-749', 'over_150m', 'noneOriginal', []],
    ['1-9', 'over_150m', 'noneOriginal', ['maybeSme']],
  ] as const)('%s staff, %s: %s', (staff, turnover, line, caveats) => {
    const note = describeSize(staff, turnover, 'original')
    expect(note?.line).toBe(line)
    expect(note?.caveats).toEqual(caveats)
    expect(note?.quotes).not.toContain('art99_6a')
  })

  it('is null until both bands are set', () => {
    expect(describeSize('1-9', null, 'original')).toBeNull()
  })
})
