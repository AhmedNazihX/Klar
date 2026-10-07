import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { CLASSIFY_URL, sseBody, WORKED_EXAMPLE_EVENTS } from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { createTestQueryClient } from '@/test/test-utils'

import { useClassify } from './use-classify'

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
})
