import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { FollowUpQuestion } from '@/api'
import type { ClassificationRun } from '@/features/classify/classification-store'
import {
  answerableQuestions,
  answersOf,
  askedQuestions,
  confirmation,
  mergeAnswers,
  profileDrafts,
  type AnswerDraft,
  type AnswerDrafts,
} from '@/features/classify/follow-up-answers'
import type { AnswerProps } from '@/features/classify/FollowUpQuestions'
import type { Answers } from '@/lib/tool-runs'

import type { FollowUpRun } from './use-follow-up-run'
import { useUserDataOverview } from './use-user-data-overview'

export type FollowUpAnswers = {
  /** The question that decides a paused result, if any. */
  deciding: FollowUpQuestion | null
  /** The other questions, for the questions panel (not the facts the cards confirm). */
  others: FollowUpQuestion[]
  /** What the question panels need. */
  answerProps: AnswerProps
  /** Confirm on an assumed fact: runs the checks again with the fact stated. */
  confirm: (fact: string) => void
  /** Try again after a failed re-run: what that run sent, with the panels' answers as they are
   *  now when it was the panels' run. */
  tryAgain: () => void
}

/**
 * The answers the user is giving on a result (story P5b): the drafts of every question, the
 * company profile's pre-selected answers (decision 026 item 2), facts confirmed, and the re-run
 * they start through `followUp`. A run sends the answers given so far with the ones the run
 * already used, so the engine always reads all of them (decision 019). Confirm on a fact card
 * sends only that confirmation with the run's answers: drafts and profile pre-fills go only when
 * the user runs the panel. Keyed by the run (the screen remounts it), so a new run starts with
 * empty drafts.
 */
export function useFollowUpAnswers(run: ClassificationRun, followUp: FollowUpRun): FollowUpAnswers {
  const { t } = useTranslation()
  const profile = useUserDataOverview().data?.profile ?? null
  const [drafts, setDrafts] = useState<AnswerDrafts>({})
  const [confirmed, setConfirmed] = useState<Answers>({})
  // Whether the last run was a fact card's Confirm, so Try again repeats that, not the panels.
  const [wasConfirm, setWasConfirm] = useState(false)

  const { deciding, others } = askedQuestions(run.result)
  const questions = deciding ? [deciding, ...others] : others
  // The profile's answers are only pre-selected; anything the user picks replaces them.
  const shown: AnswerDrafts = { ...profileDrafts(questions, profile), ...drafts }
  const given = answersOf(t, questions, shown)

  function sendPanels(): void {
    setWasConfirm(false)
    followUp.rerun(mergeAnswers(run.answers, { ...given, ...confirmed }))
  }

  function sendConfirmed(added: Answers = {}): void {
    setWasConfirm(true)
    followUp.rerun(mergeAnswers(run.answers, { ...confirmed, ...added }))
  }

  function confirm(fact: string): void {
    // The engine's own "Please confirm" question is answered when it asked one (not shown in the
    // panel: the card's Confirm stands for it).
    const asked = answerableQuestions(run.result)
    const added = confirmation(t, asked, { ...run.answers, ...confirmed }, fact)
    setConfirmed((earlier) => ({ ...earlier, ...added }))
    sendConfirmed(added)
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
      onRunAgain: sendPanels,
    },
    confirm,
    tryAgain: () => {
      if (wasConfirm) sendConfirmed()
      else sendPanels()
    },
  }
}
