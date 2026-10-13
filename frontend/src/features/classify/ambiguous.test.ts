import { describe, expect, it } from 'vitest'

import type { ClassificationResult, FollowUpQuestion } from '@/api'
import { RECORDED_AMBIGUOUS } from '@/test/ambiguous-fixtures'

import { openPoint, questionsOnPoint, type OpenPoint } from './ambiguous'

/** A question about `about`, quoting `citations` when given. */
function question(id: string, about: string, citations: string[] = []): FollowUpQuestion {
  const [quoted] = RECORDED_AMBIGUOUS.steps.flatMap((step) => step.citations ?? [])
  if (!quoted) throw new Error('The recorded result cites nothing.')
  return {
    id,
    text: `Question ${id}?`,
    about,
    options: ['yes', 'no', 'not_sure'],
    citations: citations.map((provisionId) => ({ ...quoted, provision_id: provisionId })),
  }
}

/** The recorded result open on `readingCites` (what both readings cite), its step citing
 *  `stepCites` besides, as the engine's high-risk step does. */
function pointOn(readingCites: string, stepCites: string[] = [readingCites]): OpenPoint {
  const result: ClassificationResult = {
    ...RECORDED_AMBIGUOUS,
    steps: RECORDED_AMBIGUOUS.steps.map((step) => {
      const question = step.open_question
      const [cited] = step.citations ?? []
      if (!question || !cited) return step
      const readings = question.readings.map((reading) => ({
        ...reading,
        citation: { ...cited, provision_id: readingCites },
      })) as typeof question.readings
      return {
        ...step,
        citations: stepCites.map((provisionId) => ({ ...cited, provision_id: provisionId })),
        open_question: { ...question, readings },
      }
    }),
  }
  const point = openPoint(result)
  if (!point) throw new Error('The recorded result has no open point.')
  return point
}

function split(point: OpenPoint, questions: FollowUpQuestion[]): [string[], string[]] {
  const { onPoint, elsewhere } = questionsOnPoint(questions, point)
  return [onPoint.map((asked) => asked.id), elsewhere.map((asked) => asked.id)]
}

describe('openPoint', () => {
  it('holds the provisions the readings cite, not the rest of the step’s citations', () => {
    // The recorded step also cites Annex I point A(8); both readings cite Art. 6(1).
    const step = RECORDED_AMBIGUOUS.steps.find((candidate) => candidate.open_question)
    expect(step?.citations?.map((citation) => citation.provision_id)).toContain('annex:I:A:8')
    expect(openPoint(RECORDED_AMBIGUOUS)?.provisions).toEqual(['art:6:1', 'art:6:1'])
  })
})

describe('questionsOnPoint', () => {
  it('keeps an Annex I fact elsewhere while an Annex III point is open', () => {
    // The engine's Annex III step cites Art. 6(2) and 6(3) beside the point (high_risk.py).
    const point = pointOn('annex:III:5:a', ['annex:III:5:a', 'art:6:2', 'art:6:3'])
    expect(
      split(point, [question('third_party', 'art:6:1:b'), question('benefits', 'annex:III:5:a')]),
    ).toEqual([['benefits'], ['third_party']])
  })

  it('keeps the Art. 6(3) filter, Art. 6(2) and Art. 6 whole elsewhere while Art. 6(1) is open', () => {
    const point = pointOn('art:6:1', ['annex:I:A:8', 'art:6:1'])
    expect(
      split(point, [
        question('exemption', 'art:6:3'),
        question('listed', 'art:6:2'),
        question('any_route', 'art:6'),
        question('safety', 'art:6:1:a'),
        question('assessment', 'art:6:1:b'),
      ]),
    ).toEqual([
      ['safety', 'assessment'],
      ['exemption', 'listed', 'any_route'],
    ])
  })

  it('counts a question quoting the open provision as on the point', () => {
    const point = pointOn('art:6:1', ['annex:I:A:8', 'art:6:1'])
    expect(
      split(point, [
        question('quoting', 'annex:I:A:8', ['annex:I:A:8', 'art:6:1']),
        question('role', 'art:25:1:b', ['art:25:1']),
      ]),
    ).toEqual([['quoting'], ['role']])
  })

  it('counts a question about the paragraph an open point belongs to, never its whole article', () => {
    const point = pointOn('art:6:1:a', ['art:6:1:a'])
    expect(
      split(point, [
        question('paragraph', 'art:6:1'),
        question('article', 'art:6'),
        question('sibling', 'art:6:1:b'),
      ]),
    ).toEqual([['paragraph'], ['article', 'sibling']])
    const area = pointOn('annex:III:5:a', ['annex:III:5:a'])
    expect(split(area, [question('area', 'annex:III:5'), question('annex', 'annex:III')])).toEqual([
      ['area'],
      ['annex'],
    ])
  })

  it('falls back on the step’s citations when the readings cite nothing', () => {
    const step = RECORDED_AMBIGUOUS.steps.find((candidate) => candidate.open_question)
    const open = step?.open_question
    if (!step || !open) throw new Error('The recorded result has no open question.')
    const readings = open.readings.map((reading) => ({
      ...reading,
      citation: null,
    })) as typeof open.readings
    const uncited: ClassificationResult = {
      ...RECORDED_AMBIGUOUS,
      steps: RECORDED_AMBIGUOUS.steps.map((candidate) =>
        candidate === step ? { ...step, open_question: { ...open, readings } } : candidate,
      ),
    }
    const point = openPoint(uncited)
    if (!point) throw new Error('No open point.')
    expect(point.provisions).toEqual(step.citations?.map((citation) => citation.provision_id))
    expect(split(point, [question('safety', 'art:6:1:a'), question('role', 'art:25:1')])).toEqual([
      ['safety'],
      ['role'],
    ])
  })

  it('never matches a provision that only shares a prefix of its number', () => {
    expect(
      split(pointOn('art:50:1'), [
        question('deep_fake', 'art:50:4'),
        question('chatbot', 'art:50:1'),
      ]),
    ).toEqual([['chatbot'], ['deep_fake']])
    expect(split(pointOn('art:6:1'), [question('eleven', 'art:6:11')])).toEqual([[], ['eleven']])
  })
})
