import type { ClassifyResponse, StepName, StepResult } from '@/api'
import type { CheckProgressState } from '@/components/CheckProgress'

/** The rows of the live check list, in the engine's order: the facts, the four checks in the
 *  Act's order, then the role and its duties. */
export const CHECK_IDS = [
  'facts',
  'scope',
  'prohibited',
  'high_risk',
  'transparency',
  'role_obligations',
] as const
export type CheckId = (typeof CHECK_IDS)[number]

/** The four checks the "Stopped at check N of 4" line counts. */
const NUMBERED_CHECKS: readonly StepName[] = ['scope', 'prohibited', 'high_risk', 'transparency']

/** What the stream has said so far. */
export type ProgressState = {
  facts: { count: number; questions: number } | null
  started: readonly StepName[]
  steps: Partial<Record<StepName, { result: StepResult; matches: readonly string[] }>>
  /** The row a failed run stopped at, or null. */
  stoppedAt: CheckId | null
}

export const INITIAL_PROGRESS: ProgressState = {
  facts: null,
  started: [],
  steps: {},
  stoppedAt: null,
}

export type ProgressAction =
  { type: 'reset' } | { type: 'event'; event: ClassifyResponse } | { type: 'stopped' }

// The engine's error event names a node; finalize belongs to the last row.
const NODE_ROWS: Record<string, CheckId> = {
  facts: 'facts',
  scope: 'scope',
  prohibited: 'prohibited',
  high_risk: 'high_risk',
  transparency: 'transparency',
  role_obligations: 'role_obligations',
  finalize: 'role_obligations',
}

/** The row a node id belongs to; an unknown id falls on the first row not yet finished. */
function rowOfNode(node: string, state: ProgressState): CheckId {
  return NODE_ROWS[node] ?? firstOpenRow(state)
}

function isFinished(id: CheckId, state: ProgressState): boolean {
  return id === 'facts' ? state.facts !== null : state.steps[id] !== undefined
}

function firstOpenRow(state: ProgressState): CheckId {
  return CHECK_IDS.find((id) => !isFinished(id, state)) ?? 'role_obligations'
}

function applyEvent(state: ProgressState, event: ClassifyResponse): ProgressState {
  switch (event.event) {
    case 'facts':
      return {
        ...state,
        facts: { count: event.facts.length, questions: event.follow_up_questions.length },
      }
    case 'step_started':
      return { ...state, started: [...state.started, event.step] }
    case 'step':
      return {
        ...state,
        steps: {
          ...state.steps,
          [event.step.step]: { result: event.step, matches: event.matches ?? [] },
        },
      }
    case 'error':
      return { ...state, stoppedAt: rowOfNode(event.step, state) }
    case 'result':
      return state
  }
}

/** The check list's state from the stream's events. A run that fails without an error event
 *  (the connection drops) stops at the first row not yet finished. */
export function progressReducer(state: ProgressState, action: ProgressAction): ProgressState {
  switch (action.type) {
    case 'reset':
      return INITIAL_PROGRESS
    case 'event':
      return applyEvent(state, action.event)
    case 'stopped':
      return state.stoppedAt === null ? { ...state, stoppedAt: firstOpenRow(state) } : state
  }
}

/** One row's state. While nothing has started, every row waits. */
export function checkState(
  id: CheckId,
  state: ProgressState,
  isRunning: boolean,
): CheckProgressState {
  if (state.stoppedAt === id) return 'error'
  if (id === 'facts') {
    if (state.facts) return 'done'
    return isRunning && state.stoppedAt === null ? 'running' : 'waiting'
  }
  const step = state.steps[id]
  if (step) return step.result.status === 'needs_more_information' ? 'paused' : 'done'
  if (state.stoppedAt === null && isRunning && state.started.includes(id)) return 'running'
  return 'waiting'
}

/** Whether a later check started after this one: it let the run go on. */
export function didContinue(id: StepName, state: ProgressState): boolean {
  const index = CHECK_IDS.indexOf(id)
  return state.started.some((started) => CHECK_IDS.indexOf(started) > index)
}

/** "Stopped at check N of 4": the check's number, or null for the facts and the duties. */
export function checkNumber(id: CheckId): number | null {
  const index = NUMBERED_CHECKS.indexOf(id as StepName)
  return index === -1 ? null : index + 1
}
