import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { FollowUpQuestion } from '@/api'
import type { ClassificationRun } from '@/features/classify/classification-store'
import {
  answersOf,
  confirmation,
  answerableQuestions,
  mergeAnswers,
  profileDrafts,
  type AnswerDraft,
  type AnswerDrafts,
} from '@/features/classify/follow-up-answers'
import type { AnswerProps } from '@/features/classify/FollowUpQuestions'
import { pausedStep } from '@/features/classify/result-text'
import type { Answers } from '@/lib/tool-runs'

import type { FollowUpRun } from './use-follow-up-run'
import { useUserDataOverview } from './use-user-data-overview'

function isPaused(result: ClassificationRun['result']): boolean {
  return result.status === 'needs_more_information'
}

export type FollowUpAnswers = {
  /** The question that decides a paused result, if any. */
  deciding: FollowUpQuestion | null
  /** The other questions, for "Please confirm N facts". */
  others: FollowUpQuestion[]
  /** What the question panels need. */
  answerProps: AnswerProps
  /** Confirm on an assumed fact: runs the checks again with the fact stated. */
  confirm: (fact: string) => void
  /** Try again after a failed re-run: the same answers as now. */
  tryAgain: () => void
}

/**
 * The answers the user is giving on a result (story P5b): the drafts of every question, the
 * company profile's pre-selected answers (decision 026 item 2), facts confirmed, and the re-run
 * they start through `followUp`. A run sends the answers given so far with the ones the run
 * already used, so the engine always reads all of them (decision 019). Keyed by the run (the
 * screen remounts it), so a new run starts with empty drafts.
 */
export function useFollowUpAnswers(run: ClassificationRun, followUp: FollowUpRun): FollowUpAnswers {
  const { t } = useTranslation()
  const profile = useUserDataOverview().data?.profile ?? null
  const [drafts, setDrafts] = useState<AnswerDrafts>({})
  const [confirmed, setConfirmed] = useState<Answers>({})

  const deciding = isPaused(run.result) ? (pausedStep(run.result)?.missing_fact ?? null) : null
  const others = answerableQuestions(run.result).filter((question) => question.id !== deciding?.id)
  const questions = deciding ? [deciding, ...others] : others
  // The profile's answers are only pre-selected; anything the user picks replaces them.
  const shown: AnswerDrafts = { ...profileDrafts(questions, profile), ...drafts }
  const given = answersOf(t, questions, shown)

  function send(extra: Answers = {}): void {
    followUp.rerun(mergeAnswers(run.answers, { ...given, ...confirmed, ...extra }))
  }

  function confirm(fact: string): void {
    const added = confirmation(t, questions, { ...run.answers, ...confirmed }, fact)
    setConfirmed((earlier) => ({ ...earlier, ...added }))
    send(added)
  }

  return {
    deciding,
    others,
    answerProps: {
      drafts: shown,
      onDraftChange: (id: string, draft: AnswerDraft) => {
        setDrafts((earlier) => ({ ...earlier, [id]: draft }))
      },
      hasAnswers: Object.keys(given).length > 0,
      isRunning: followUp.isRunning,
      onRunAgain: () => {
        send()
      },
    },
    confirm,
    tryAgain: () => {
      send()
    },
  }
}
