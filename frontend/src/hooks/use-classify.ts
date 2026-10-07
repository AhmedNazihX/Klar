import { useMutation, type UseMutationResult } from '@tanstack/react-query'
import { useEffect, useReducer, useRef, type Dispatch } from 'react'

import { classify, type ClassificationResult, type ClassifyRequest } from '@/api'
import {
  INITIAL_PROGRESS,
  progressReducer,
  type ProgressAction,
  type ProgressState,
} from '@/features/classify/classify-progress'
import { SSE_MAX_RETRY_ATTEMPTS } from '@/lib/api-client-config'

/** Why a run ended without a result. Klar never shows a class after any of these. */
export type ClassifyFailure =
  /** The engine's error event: a check couldn't finish (`node` is the engine's node id). */
  | { kind: 'check'; node: string; message: string }
  /** The API refused the run before it started: 503 busy or not configured, 429, 422, 413… */
  | { kind: 'http'; status: number; retryAfterSeconds: number | null }
  /** No answer at all: offline, a refused connection, CORS. */
  | { kind: 'network' }
  /** The stream ended before a result or an error came. */
  | { kind: 'incomplete' }

export class ClassifyRunError extends Error {
  readonly failure: ClassifyFailure

  constructor(failure: ClassifyFailure) {
    super(`classification stopped: ${failure.kind}`)
    this.name = 'ClassifyRunError'
    this.failure = failure
  }
}

function retryAfterSeconds(response: Response): number | null {
  const header = response.headers.get('Retry-After')
  if (header === null) return null
  const seconds = Number.parseInt(header, 10)
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null
}

/** A run stopped because a newer one replaced it or the screen went: nothing of it may reach
 *  the check list any more, which belongs to the next run. */
function stoppedByCaller(): DOMException {
  return new DOMException('The classification was stopped.', 'AbortError')
}

/**
 * Runs one classification over `POST /classify` and feeds every streamed event to `dispatch`.
 * Resolves with the result, or rejects with a ClassifyRunError. The SSE client never retries
 * (each run is paid; pinned on this call too, so no per-call option can turn retries on) and
 * ends a failed stream without throwing, so the HTTP status is read from the response itself.
 * Once `signal` aborts, nothing more is dispatched.
 */
async function runClassification(
  body: ClassifyRequest,
  dispatch: Dispatch<ProgressAction>,
  signal: AbortSignal,
): Promise<ClassificationResult> {
  // Filled in by the client's callbacks while the stream runs.
  const seen: { refused: ClassifyFailure | null; hasStreamFailed: boolean } = {
    refused: null,
    hasStreamFailed: false,
  }
  const { stream } = await classify({
    body,
    signal,
    sseMaxRetryAttempts: SSE_MAX_RETRY_ATTEMPTS,
    fetch: async (input: URL | RequestInfo, init?: RequestInit) => {
      const response = await globalThis.fetch(input, init)
      if (!response.ok) {
        seen.refused = {
          kind: 'http',
          status: response.status,
          retryAfterSeconds: retryAfterSeconds(response),
        }
      }
      return response
    },
    onSseError: () => {
      seen.hasStreamFailed = true
    },
  })
  for await (const event of stream) {
    if (signal.aborted) break
    dispatch({ type: 'event', event })
    if (event.event === 'error') {
      throw new ClassifyRunError({ kind: 'check', node: event.step, message: event.message })
    }
    if (event.event === 'result') return event.result
  }
  if (signal.aborted) throw stoppedByCaller()
  dispatch({ type: 'stopped' })
  if (seen.refused) throw new ClassifyRunError(seen.refused)
  throw new ClassifyRunError({ kind: seen.hasStreamFailed ? 'network' : 'incomplete' })
}

type UseClassify = {
  progress: ProgressState
  run: UseMutationResult<ClassificationResult, Error, ClassifyRequest>
}

/**
 * The Classify screen's run: the live check list and the mutation that streams one run. A run
 * starts only when the user asks (never on a retry of its own), and leaving the screen stops it.
 */
export function useClassify(): UseClassify {
  const [progress, dispatch] = useReducer(progressReducer, INITIAL_PROGRESS)
  const abortRef = useRef<AbortController | null>(null)

  // The stream is a connection outside React: close it when the screen goes.
  useEffect(
    () => () => {
      abortRef.current?.abort()
    },
    [],
  )

  const run = useMutation({
    retry: false,
    mutationFn: (body: ClassifyRequest) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      dispatch({ type: 'reset' })
      return runClassification(body, dispatch, controller.signal)
    },
  })

  return { progress, run }
}
