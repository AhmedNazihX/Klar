import { describe, expect, it } from 'vitest'

import { dutyLabel } from '@/features/classify/result-text'
import { limitedRisk, WORKED_EXAMPLE } from '@/test/classify-fixtures'
import { ambiguousResult } from '@/test/inventory-fixtures'

import { parseStoredResult } from './stored-result'

/** The worked example with its first duty changed by `fields`. */
function withFirstDuty(fields: Record<string, unknown>): unknown {
  const [first, ...rest] = WORKED_EXAMPLE.obligations ?? []
  return { ...WORKED_EXAMPLE, obligations: [{ ...first, ...fields }, ...rest] }
}

/** The worked example with its first step's first citation changed by `fields`. */
function withFirstCitation(fields: Record<string, unknown>): unknown {
  const [step, ...steps] = WORKED_EXAMPLE.steps
  const [citation, ...citations] = step?.citations ?? []
  return {
    ...WORKED_EXAMPLE,
    steps: [{ ...step, citations: [{ ...citation, ...fields }, ...citations] }, ...steps],
  }
}

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
        ({ article, applies_from, high_risk_route }) => ({
          article,
          applies_from,
          high_risk_route,
        }),
      ),
    }
    const parsed = parseStoredResult(stored)

    // The missing texts read as empty, never undefined (they key the duty lists)…
    expect(parsed?.obligations?.[1]).toEqual({
      ...stored.obligations[1],
      duty: '',
      label_en: '',
      label_de: '',
    })
    // …and a duty without its label is named by its provision, in either language.
    const [, duty] = parsed?.obligations ?? []
    if (!duty) throw new Error('The stored result keeps its duties.')
    expect(dutyLabel(duty, 'en')).toBe('Art. 26(1)')
    expect(dutyLabel(duty, 'de')).toBe('Art. 26 Abs. 1')
    expect(parsed?.law_text).toBeUndefined()
    // A duty stored before P24 has no key: it loads, with nothing to tick.
    expect(duty.key).toBeUndefined()
  })

  it('keeps a duty key of 200 characters', () => {
    const key = 'a'.repeat(200)
    expect(parseStoredResult(withFirstDuty({ key }))?.obligations?.[0]?.key).toBe(key)
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
    ['a duty without its date', withFirstDuty({ applies_from: 'soon' })],
    ['an as-of that is no date', { ...WORKED_EXAMPLE, as_of: 'yesterday' }],
    ['an English label that is no text', withFirstDuty({ label_en: { x: 1 } })],
    ['a German label that is no text', withFirstDuty({ label_de: 7 })],
    ['a duty that is no text', withFirstDuty({ duty: ['comply'] })],
    ['a duty key that is no table key', withFirstDuty({ key: 'Drop table;' })],
    ['a duty key past 200 characters', withFirstDuty({ key: 'a'.repeat(201) })],
    ['a duty key that is no text', withFirstDuty({ key: 7 })],
    [
      'a CELEX number that is no text',
      { ...WORKED_EXAMPLE, law_text: { ...WORKED_EXAMPLE.law_text, celex: 2024 } },
    ],
    ['a citation without its document', withFirstCitation({ document_id: undefined })],
  ])('refuses a result with %s', (_, stored) => {
    expect(parseStoredResult(stored)).toBeNull()
  })
})
