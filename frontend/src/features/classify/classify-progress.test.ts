import { describe, expect, it } from 'vitest'

import type { ClassifyResponse } from '@/api'
import { WORKED_EXAMPLE_EVENTS } from '@/test/classify-fixtures'

import {
  CHECK_IDS,
  checkNumber,
  checkState,
  INITIAL_PROGRESS,
  progressReducer,
  type ProgressState,
} from './classify-progress'

function replay(events: readonly ClassifyResponse[]): ProgressState {
  return events.reduce(
    (state, event) => progressReducer(state, { type: 'event', event }),
    INITIAL_PROGRESS,
  )
}

function states(state: ProgressState, isRunning: boolean): string[] {
  return CHECK_IDS.map((id) => checkState(id, state, isRunning))
}

describe('progressReducer', () => {
  it('waits on every row before a run, and reads the facts first once it starts', () => {
    expect(states(INITIAL_PROGRESS, false)).toEqual(Array(6).fill('waiting'))
    expect(states(INITIAL_PROGRESS, true)).toEqual([
      'running',
      ...new Array<string>(5).fill('waiting'),
    ])
  })

  it('follows the recorded worked example to the end', () => {
    const state = replay(WORKED_EXAMPLE_EVENTS)
    expect(states(state, false)).toEqual(['done', 'paused', 'done', 'done', 'done', 'done'])
    expect(state.facts).toEqual({ count: 4, questions: 5 })
    expect(state.steps.high_risk?.matches).toEqual(['annex:III:4:a'])
  })

  it('marks the started step running until its result arrives', () => {
    const upToHighRisk = WORKED_EXAMPLE_EVENTS.findIndex(
      (event) => event.event === 'step_started' && event.step === 'high_risk',
    )
    const state = replay(WORKED_EXAMPLE_EVENTS.slice(0, upToHighRisk + 1))
    expect(checkState('high_risk', state, true)).toBe('running')
    expect(checkState('transparency', state, true)).toBe('waiting')
  })

  it('stops at the node the error event names, finalize on the last row', () => {
    const failed = progressReducer(INITIAL_PROGRESS, {
      type: 'event',
      event: { event: 'error', step: 'finalize', message: 'x' },
    })
    expect(failed.stoppedAt).toBe('role_obligations')
    expect(checkState('role_obligations', failed, false)).toBe('error')
  })

  it('stops a dropped stream at the first row not yet finished', () => {
    const state = replay(WORKED_EXAMPLE_EVENTS.slice(0, 1))
    expect(progressReducer(state, { type: 'stopped' }).stoppedAt).toBe('scope')
    expect(progressReducer(state, { type: 'reset' })).toBe(INITIAL_PROGRESS)
  })

  it('numbers the four checks only', () => {
    expect(CHECK_IDS.map(checkNumber)).toEqual([null, 1, 2, 3, 4, null])
  })
})
