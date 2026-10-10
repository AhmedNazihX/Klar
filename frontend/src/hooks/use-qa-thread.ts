import { useMutation } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { askQuestion, type ClassificationResult, type LawVersion, type QaAnswer } from '@/api'
import { readThread, writeThread, type QaEntry } from '@/features/ask/qa-history'
import type { Language } from '@/i18n'

import { useLanguage } from './use-language'

const TOO_MANY_REQUESTS = 429

export class QaError extends Error {
  readonly status: number | null

  constructor(status: number | null) {
    super(`question failed: ${String(status)}`)
    this.name = 'QaError'
    this.status = status
  }
}

/** One question sent, with the thread it was asked in. */
type Asked = { id: string; question: string; language: Language; thread: string }

export type QaThread = {
  entries: readonly QaEntry[]
  /** Ask a question in the screen's language. Nothing is sent while an answer is on its way. */
  ask: (question: string) => void
  /** Ask a failed question again: only ever on the user's click, never by itself. */
  retry: (id: string) => void
  isAsking: boolean
}

function newId(): string {
  return crypto.randomUUID()
}

/**
 * One conversation with Klar (`POST /qa`, P7): the Ask page's, or the one about a result, which
 * sends the result with each question so its answer cites the result's provisions. The answered
 * questions stay for the browser session (`qa-history`); nothing goes to the database. A result's
 * thread is held above its view switch (`ResultScreen`), so an answer still on its way lands in
 * the thread whichever view is shown; a new `thread` (the next run) starts from its own history.
 * An answer that comes back after the screen moved to another thread is kept in its own thread's
 * history (a failure there is dropped: it is asked again by the user), and the new thread's field
 * is free at once.
 */
export function useQaThread(
  thread: string,
  { lawVersion, result }: { lawVersion: LawVersion; result?: ClassificationResult },
): QaThread {
  const language = useLanguage()
  const [held, setHeld] = useState<{ thread: string; entries: QaEntry[] }>(() => ({
    thread,
    entries: readThread(thread),
  }))
  if (held.thread !== thread) {
    // Another run's thread: switch to its history while rendering (no effect, no flash).
    setHeld({ thread, entries: readThread(thread) })
  }
  const entries = held.thread === thread ? held.entries : []

  useEffect(() => {
    writeThread(held.thread, held.entries)
  }, [held])

  function setEntries(update: (current: QaEntry[]) => QaEntry[]): void {
    setHeld((current) => ({ ...current, entries: update(current.entries) }))
  }

  /** Settles a question in the thread shown; one asked in another thread is left alone. */
  function settle({ id, thread: asked }: Asked, update: Partial<QaEntry>): void {
    setHeld((current) =>
      current.thread === asked
        ? {
            ...current,
            entries: current.entries.map((entry) =>
              entry.id === id ? { ...entry, ...update } : entry,
            ),
          }
        : current,
    )
  }

  const mutation = useMutation({
    mutationFn: async ({ question, language: asked }: Asked): Promise<QaAnswer> => {
      const { data, response } = await askQuestion({
        body: { question, language: asked, law_version: lawVersion, result: result ?? null },
      })
      if (!response?.ok || !data) throw new QaError(response?.status ?? null)
      return data
    },
    onSuccess: (answer, asked) => {
      if (asked.thread !== thread) {
        // The screen moved on (the next run): keep the answer in its own thread's history.
        const { id, question } = asked
        writeThread(asked.thread, [
          ...readThread(asked.thread),
          { id, question, state: 'answered', answer },
        ])
        return
      }
      settle(asked, { state: 'answered', answer, failure: undefined })
    },
    onError: (error, asked) => {
      const isBusy = error instanceof QaError && error.status === TOO_MANY_REQUESTS
      settle(asked, { state: 'failed', failure: isBusy ? 'busy' : 'failed' })
    },
  })

  function send(asked: Asked): void {
    mutation.mutate(asked)
  }

  // Only a question of this thread holds its field: one still on its way from another thread
  // (the run before) doesn't.
  const isAsking = mutation.isPending && mutation.variables.thread === thread

  return {
    entries,
    ask: (question) => {
      if (isAsking) return
      const asked = { id: newId(), question, language, thread }
      setEntries((current) => [...current, { id: asked.id, question, state: 'pending' }])
      send(asked)
    },
    retry: (id) => {
      const failed = entries.find((entry) => entry.id === id && entry.state === 'failed')
      if (!failed || isAsking) return
      const asked = { id, question: failed.question, language, thread }
      settle(asked, { state: 'pending', failure: undefined })
      send(asked)
    },
    isAsking,
  }
}
