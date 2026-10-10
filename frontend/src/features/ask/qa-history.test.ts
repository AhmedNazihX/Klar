import { beforeEach, describe, expect, it } from 'vitest'

import { answered } from '@/test/qa-fixtures'

import {
  MAX_KEPT_QUESTIONS,
  readThread,
  resultThread,
  writeThread,
  type QaEntry,
} from './qa-history'

const KEY = 'klar.qa.ask'

beforeEach(() => {
  window.sessionStorage.clear()
})

describe('qa-history', () => {
  it('keeps only answered questions, in order', () => {
    const entries: QaEntry[] = [
      { id: 'a', question: 'One?', state: 'answered', answer: answered() },
      { id: 'b', question: 'Two?', state: 'failed', failure: 'failed' },
      { id: 'c', question: 'Three?', state: 'pending' },
    ]
    writeThread('ask', entries)
    expect(readThread('ask').map((entry) => [entry.id, entry.state])).toEqual([['a', 'answered']])
  })

  it.each(['answered', 'outside_corpus', 'compliance', 'refused'] as const)(
    'keeps a %s answer across a reload',
    (kind) => {
      const answer = { ...answered(), kind, citations: [] }
      writeThread('ask', [{ id: 'a', question: 'Q?', state: 'answered', answer }])
      expect(readThread('ask')).toEqual([{ id: 'a', question: 'Q?', state: 'answered', answer }])
    },
  )

  it('keeps the latest questions only', () => {
    const entries: QaEntry[] = Array.from({ length: MAX_KEPT_QUESTIONS + 2 }, (_, n) => ({
      id: `q${String(n)}`,
      question: `Q${String(n)}?`,
      state: 'answered',
      answer: answered(),
    }))
    writeThread('ask', entries)
    const kept = readThread('ask')
    expect(kept).toHaveLength(MAX_KEPT_QUESTIONS)
    expect(kept[0]?.id).toBe('q2')
  })

  it.each([
    ['not JSON', '{'],
    ['not a list', '{"id": "a"}'],
    [
      'an unknown kind',
      JSON.stringify([{ id: 'a', question: 'Q?', answer: { ...answered(), kind: 'maybe' } }]),
    ],
    [
      'a citation without a quote',
      JSON.stringify([
        {
          id: 'a',
          question: 'Q?',
          answer: {
            ...answered(),
            citations: [{ provision_id: 'art:1', document_id: 'x', language: 'en' }],
          },
        },
      ]),
    ],
  ])('starts empty from %s', (_, raw) => {
    window.sessionStorage.setItem(KEY, raw)
    expect(readThread('ask')).toEqual([])
  })

  it('names a thread per tool and run', () => {
    expect(resultThread('tool-1', 2)).toBe('result.tool-1.2')
  })
})
