import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import type { ClassifyResponse } from '@/api'
import {
  CLASSIFY_URL,
  classifyHandler,
  needsDescriptionEvents,
  PERSON_REVIEW,
  providerRefused,
  sseBody,
  WORKED_EXAMPLE_EVENTS,
} from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { createTestQueryClient } from '@/test/test-utils'

import { ClassifyRunError, useClassify } from './use-classify'

function renderUseClassify() {
  const client = createTestQueryClient()
  return renderHook(() => useClassify(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  })
}

const BODY = { description: 'A tool that ranks job applications.', language: 'en' } as const

describe('useClassify', () => {
  it("leaves a replaced run's ending off the next run's check list", async () => {
    // The first run streams its facts, then hangs; the second never answers.
    const encoder = new TextEncoder()
    let requests = 0
    server.use(
      http.post(CLASSIFY_URL, () => {
        requests += 1
        const events = requests === 1 ? WORKED_EXAMPLE_EVENTS.slice(0, 1) : []
        const stream = new ReadableStream({
          async start(controller) {
            controller.enqueue(encoder.encode(sseBody(events)))
            await delay('infinite')
          },
        })
        return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
      }),
    )
    const { result } = renderUseClassify()

    let first: Promise<unknown> = Promise.resolve()
    act(() => {
      first = result.current.run.mutateAsync(BODY).catch((error: unknown) => error)
    })
    await waitFor(() => {
      expect(result.current.progress.facts).not.toBeNull()
    })
    act(() => {
      result.current.run.mutate(BODY)
    })

    // Once the first run's promise settles, it has done everything it was going to do.
    const firstError = await first
    await waitFor(() => {
      expect(requests).toBe(2)
    })
    expect(result.current.progress.stoppedAt).toBeNull()
    expect(result.current.progress.facts).toBeNull()
    expect(result.current.run.isPending).toBe(true)
    expect(firstError).toBeInstanceOf(DOMException)
  })

  it('ends a needs-a-description run without a class with its three prompts', async () => {
    // E13: the description was too thin to start, so no check ran and no class was given.
    server.use(classifyHandler(needsDescriptionEvents()))
    const { result } = renderUseClassify()

    let outcome: unknown
    await act(async () => {
      outcome = await result.current.run.mutateAsync(BODY).catch((error: unknown) => error)
    })

    expect(outcome).toBeInstanceOf(ClassifyRunError)
    const failure = (outcome as ClassifyRunError).failure
    expect(failure.kind).toBe('needs_description')
    const questions = failure.kind === 'needs_description' ? failure.questions : []
    expect(questions.map((question) => [question.id, question.text, question.hint])).toEqual([
      [
        'what_it_decides',
        'What does it decide or suggest?',
        'For example: it ranks applicants, answers staff questions, plans shifts.',
      ],
      ['who_it_affects', 'Who does it affect?', 'For example: applicants, your staff, customers.'],
      [
        'bought_or_built',
        'Did you buy it or build it?',
        'And whether you changed it or put your own name on it.',
      ],
    ])
    expect(result.current.progress.started).toEqual([])
  })

  it('stops a run whose check the provider refused with the blocked checks and the review question', async () => {
    // Decision 030: a refused check gives no class, but the result still lists every step.
    const refused: ClassifyResponse = { event: 'result', result: providerRefused() }
    server.use(classifyHandler([...WORKED_EXAMPLE_EVENTS.slice(0, 1), refused]))
    const { result } = renderUseClassify()

    let outcome: unknown
    await act(async () => {
      outcome = await result.current.run.mutateAsync(BODY).catch((error: unknown) => error)
    })

    expect(outcome).toBeInstanceOf(ClassifyRunError)
    expect((outcome as ClassifyRunError).failure).toEqual({
      kind: 'provider_refused',
      steps: ['prohibited'],
      questions: [PERSON_REVIEW.text],
    })
  })
})
