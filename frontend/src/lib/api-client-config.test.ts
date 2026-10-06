import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { classify } from '@/api'
import { server } from '@/test/msw-server'

import { createClientConfig, SSE_MAX_RETRY_ATTEMPTS } from './api-client-config'
import { env } from './env'

describe('createClientConfig', () => {
  it('turns off SSE retries', () => {
    expect(createClientConfig({}).sseMaxRetryAttempts).toBe(SSE_MAX_RETRY_ATTEMPTS)
    expect(SSE_MAX_RETRY_ATTEMPTS).toBe(1)
  })
})

describe('classify', () => {
  it('does not retry a failed run, which would start a second paid classification', async () => {
    // A retry would reach the handler again without waiting (the no-op sleep), and the second
    // request aborts the stream, so a regression fails the request count below at once instead
    // of looping or timing out.
    const controller = new AbortController()
    let requests = 0
    server.use(
      http.post(`${env.apiUrl}/classify`, () => {
        requests += 1
        if (requests > 1) controller.abort()
        return HttpResponse.json({ detail: 'busy' }, { status: 503 })
      }),
    )
    const onSseError = vi.fn()
    const { stream } = await classify({
      body: { description: 'A chatbot that answers customer questions.', language: 'en' },
      onSseError,
      signal: controller.signal,
      // Not in the generated options type, but passed through to the SSE client.
      ...{ sseSleepFn: () => Promise.resolve() },
    })
    const events: unknown[] = []
    for await (const event of stream) events.push(event)

    expect(requests).toBe(1)
    expect(onSseError).toHaveBeenCalledTimes(1)
    expect(events).toEqual([])
  })
})
