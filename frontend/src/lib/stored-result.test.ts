import { describe, expect, it } from 'vitest'

import { limitedRisk, WORKED_EXAMPLE } from '@/test/classify-fixtures'
import { ambiguousResult } from '@/test/inventory-fixtures'

import { parseStoredResult } from './stored-result'

describe('parseStoredResult', () => {
  it.each([
    ['the recorded worked example', WORKED_EXAMPLE],
    ['a limited-risk result', limitedRisk()],
    ['a legally ambiguous result', ambiguousResult()],
  ])('keeps %s as stored', (_, result) => {
    expect(parseStoredResult(result)).toEqual(result)
  })

  it('still reads a result stored before the duty texts and E12 fields existed', () => {
    const stored = {
      ...WORKED_EXAMPLE,
      law_text: undefined,
      follow_up_questions: undefined,
      obligations: (WORKED_EXAMPLE.obligations ?? []).map(
        ({ article, applies_from, high_risk_route, duty }) => ({
          article,
          applies_from,
          high_risk_route,
          duty,
        }),
      ),
    }
    expect(parseStoredResult(stored)).toEqual(stored)
  })

  it.each([
    ['not an object', 'high_risk'],
    ['no class', { ...WORKED_EXAMPLE, risk_class: undefined }],
    ['a class the engine never gives', { ...WORKED_EXAMPLE, risk_class: 'harmless' }],
    ['a status the engine never gives', { ...WORKED_EXAMPLE, status: 'approved' }],
    ['steps that are not a list', { ...WORKED_EXAMPLE, steps: 'all fine' }],
    [
      'a step of an unknown check',
      { ...WORKED_EXAMPLE, steps: [{ step: 'vibes', decision: 'ok' }] },
    ],
    [
      'a duty without its date',
      {
        ...WORKED_EXAMPLE,
        obligations: [{ ...WORKED_EXAMPLE.obligations?.[0], applies_from: 'soon' }],
      },
    ],
    ['an as-of that is no date', { ...WORKED_EXAMPLE, as_of: 'yesterday' }],
  ])('refuses a result with %s', (_, stored) => {
    expect(parseStoredResult(stored)).toBeNull()
  })
})
