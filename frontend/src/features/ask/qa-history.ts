import { z } from 'zod'

import type { QaAnswer } from '@/api'

// Q&A history lives only for the browser session (decision 026 item 6): sessionStorage, so a
// refresh keeps the thread and closing the tab forgets it; nothing goes to the database. Each
// thread has its own key: the Ask page's one, and one per result run. What comes back from
// storage is untrusted (another script in the tab, a stale shape), so it is checked here; a
// thread that fails the check starts empty. Only answered questions are kept: one still on its
// way or one that failed is asked again by the user, never resent.

const STORAGE_PREFIX = 'klar.qa.'
/** The longest thread kept: older questions drop off the top. */
export const MAX_KEPT_QUESTIONS = 50

/** One question and, once it came back, its answer. */
export type QaEntry = {
  id: string
  question: string
  state: 'pending' | 'answered' | 'failed'
  answer?: QaAnswer
  /** Why it failed: too many questions in a short time, or anything else. */
  failure?: 'busy' | 'failed'
}

const CitationSchema = z.looseObject({
  provision_id: z.string(),
  document_id: z.string(),
  language: z.enum(['en', 'de']),
  quote: z.string(),
})

const AnswerSchema = z.looseObject({
  kind: z.enum(['answered', 'outside_corpus', 'compliance', 'refused']),
  answer: z.string(),
  citations: z.array(CitationSchema),
  language: z.enum(['en', 'de']),
  law_version: z.enum(['amended', 'original']),
  as_of: z.string().nullable(),
  disclaimer: z.string(),
})

const StoredSchema = z.array(
  z.object({ id: z.string(), question: z.string(), answer: AnswerSchema }),
)

/** The Ask page's thread. */
export const ASK_THREAD = 'ask'

/** A result run's thread: its tool and run number, so the next run starts afresh. */
export function resultThread(toolId: string, runNo: number): string {
  return `result.${toolId}.${String(runNo)}`
}

function storage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null // storage blocked by the browser: the thread lives in memory only
  }
}

/** The thread's answered questions from this session, oldest first; none when there are none,
 *  storage is blocked or what is stored isn't a thread. */
export function readThread(thread: string): QaEntry[] {
  const raw = storage()?.getItem(STORAGE_PREFIX + thread)
  if (!raw) return []
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return []
  }
  const stored = StoredSchema.safeParse(parsed)
  if (!stored.success) return []
  return stored.data.map((entry) => ({
    id: entry.id,
    question: entry.question,
    state: 'answered',
    // Checked above for every field the thread reads; the rest is rendered as plain text.
    answer: entry.answer,
  }))
}

/** Keep the thread's answered questions for the session (the latest `MAX_KEPT_QUESTIONS`). A
 *  full or blocked storage keeps nothing more: the thread still shows until the page goes. */
export function writeThread(thread: string, entries: readonly QaEntry[]): void {
  const answered = entries
    .filter((entry) => entry.state === 'answered' && entry.answer)
    .slice(-MAX_KEPT_QUESTIONS)
    .map(({ id, question, answer }) => ({ id, question, answer }))
  try {
    storage()?.setItem(STORAGE_PREFIX + thread, JSON.stringify(answered))
  } catch {
    // Quota exceeded: the session copy stays as it was.
  }
}
