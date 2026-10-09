import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import type { ClassifyResponse } from '@/api'
import {
  CLASSIFY_URL,
  classifyHandler,
  sseBody,
  WORKED_EXAMPLE,
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

  it('ends a needs-a-description run without a class with its three questions', async () => {
    // E13: the description was too thin to start, so no check ran and no class was given.
    const thin: ClassifyResponse = {
      event: 'result',
      result: {
        ...WORKED_EXAMPLE,
        steps: [],
        risk_class: null,
        status: 'needs_more_information',
        role: null,
        also_role: null,
        role_switch_reason: null,
        annex_point: null,
        transparency_duties: [],
        deciding_facts: [],
        obligations: [],
        legal_review: null,
        follow_up_questions: [
          { id: 'what_it_decides', text: 'What does it decide or suggest?' },
          { id: 'who_it_affects', text: 'Who does it affect?' },
          { id: 'bought_or_built', text: 'Did you buy it or build it?' },
        ],
      },
    }
    server.use(classifyHandler([...WORKED_EXAMPLE_EVENTS.slice(0, 1), thin]))
    const { result } = renderUseClassify()

    let outcome: unknown
    await act(async () => {
      outcome = await result.current.run.mutateAsync(BODY).catch((error: unknown) => error)
    })

    expect(outcome).toBeInstanceOf(ClassifyRunError)
    expect((outcome as ClassifyRunError).failure).toEqual({
      kind: 'needs_description',
      questions: [
        'What does it decide or suggest?',
        'Who does it affect?',
        'Did you buy it or build it?',
      ],
    })
  })

  it('stops a run whose check the provider refused with no class and no thin prompts', async () => {
    // Decision 030: a refused check gives no class, but the result still lists every step.
    const refused: ClassifyResponse = {
      event: 'result',
      result: {
        ...WORKED_EXAMPLE,
        risk_class: null,
        status: 'needs_more_information',
        annex_point: null,
        transparency_duties: [],
        obligations: [],
        legal_review: null,
        not_assessed: ['prohibited'],
      },
    }
    server.use(classifyHandler([...WORKED_EXAMPLE_EVENTS.slice(0, 1), refused]))
    const { result } = renderUseClassify()

    let outcome: unknown
    await act(async () => {
      outcome = await result.current.run.mutateAsync(BODY).catch((error: unknown) => error)
    })

    expect(outcome).toBeInstanceOf(ClassifyRunError)
    expect((outcome as ClassifyRunError).failure).toEqual({ kind: 'check' })
  })
})
