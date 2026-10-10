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

type Asked = { id: string; question: string; language: Language }

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
 * questions stay for the browser session (`qa-history`); nothing goes to the database.
 */
export function useQaThread(
  thread: string,
  { lawVersion, result }: { lawVersion: LawVersion; result?: ClassificationResult },
): QaThread {
  const language = useLanguage()
  const [entries, setEntries] = useState<QaEntry[]>(() => readThread(thread))

  useEffect(() => {
    writeThread(thread, entries)
  }, [thread, entries])

  function settle(id: string, update: Partial<QaEntry>): void {
    setEntries((current) =>
      current.map((entry) => (entry.id === id ? { ...entry, ...update } : entry)),
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
    onSuccess: (answer, { id }) => {
      settle(id, { state: 'answered', answer, failure: undefined })
    },
    onError: (error, { id }) => {
      const isBusy = error instanceof QaError && error.status === TOO_MANY_REQUESTS
      settle(id, { state: 'failed', failure: isBusy ? 'busy' : 'failed' })
    },
  })

  function send(asked: Asked): void {
    mutation.mutate(asked)
  }

  return {
    entries,
    ask: (question) => {
      if (mutation.isPending) return
      const asked = { id: newId(), question, language }
      setEntries((current) => [...current, { id: asked.id, question, state: 'pending' }])
      send(asked)
    },
    retry: (id) => {
      const failed = entries.find((entry) => entry.id === id && entry.state === 'failed')
      if (!failed || mutation.isPending) return
      settle(id, { state: 'pending', failure: undefined })
      send({ id, question: failed.question, language })
    },
    isAsking: mutation.isPending,
  }
}
