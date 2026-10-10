import { hashKey } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'

import type { ClassificationResult } from '@/api'
import { RECORDED_PROHIBITED } from '@/test/prohibited-fixtures'

import { letterAnswers, vendorLetterOptions } from './use-vendor-letter'

/** The key TanStack Query files the letter under, as it hashes it. */
function letterKey(result: ClassificationResult): string {
  return hashKey(vendorLetterOptions('tool', 'Name', result, 'en').queryKey)
}

describe('letterAnswers', () => {
  it('answers "The tool" with the tool’s name', () => {
    expect(letterAnswers('  Call mood scoring ')).toEqual({ tool_name: 'Call mood scoring' })
  })

  it.each([null, '', '   '])('leaves the tool to fill in without a name (%j)', (name) => {
    expect(letterAnswers(name)).toEqual({})
  })
})

describe('vendorLetterOptions', () => {
  it('files a later run of the same tool, on the same day, under its own key', () => {
    const later = { ...RECORDED_PROHIBITED, steps: RECORDED_PROHIBITED.steps.slice(0, -1) }
    expect(later.as_of).toBe(RECORDED_PROHIBITED.as_of)
    expect(letterKey(later)).not.toBe(letterKey(RECORDED_PROHIBITED))
  })

  it('files the same run under the same key, however its fields are ordered', () => {
    const { facts, ...rest } = RECORDED_PROHIBITED
    expect(letterKey({ ...rest, facts })).toBe(letterKey(RECORDED_PROHIBITED))
  })
})
