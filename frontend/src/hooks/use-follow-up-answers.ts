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
  /** The questions the company profile answers, shown apart from the open ones (P29). */
  fromProfile: FollowUpQuestion[]
  /** Change on a profile answer: the question is asked again, with nothing pre-selected. */
  changeProfileAnswer: (id: string) => void
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
 * company profile's answers (decision 026 item 2; shown apart from the open questions until the
 * user changes one, P29), facts confirmed, and the re-run they start through `followUp`. A run sends the answers given so far with the ones the run
 * already used, so the engine always reads all of them (decision 019). Confirm on a fact card
 * sends only that confirmation with the run's answers: drafts and profile answers go only when
 * the user runs the panel. Keyed by the run (the screen remounts it), so a new run starts with
 * empty drafts.
 */
export function useFollowUpAnswers(run: ClassificationRun, followUp: FollowUpRun): FollowUpAnswers {
  const { t } = useTranslation()
  const profile = useUserDataOverview().data?.profile ?? null
  const [drafts, setDrafts] = useState<AnswerDrafts>({})
  const [confirmed, setConfirmed] = useState<Answers>({})
  // The profile answers the user chose to give themselves (Change).
  const [changed, setChanged] = useState<ReadonlySet<string>>(new Set())
  // The question Change asked again last, which takes the focus.
  const [reopenedId, setReopenedId] = useState<string | null>(null)
  // Whether the last run was a fact card's Confirm, so Try again repeats that, not the panels.
  const [wasConfirm, setWasConfirm] = useState(false)

  const asked = askedQuestions(run.result)
  const questions = asked.deciding ? [asked.deciding, ...asked.others] : asked.others
  // A question the user changed or already answered stays theirs: the profile, read later than
  // their click perhaps, never replaces their answer.
  const isUsers = new Set([...changed, ...Object.keys(drafts)])
  const fromProfileDrafts = profileDrafts(questions, profile, isUsers)
  const isOpen = (question: FollowUpQuestion): boolean => !(question.id in fromProfileDrafts)
  const deciding = asked.deciding && isOpen(asked.deciding) ? asked.deciding : null
  const others = asked.others.filter(isOpen)
  const fromProfile = questions.filter((question) => !isOpen(question))
  const shown: AnswerDrafts = { ...drafts, ...fromProfileDrafts }
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
    const answerable = answerableQuestions(run.result)
    const added = confirmation(t, answerable, { ...run.answers, ...confirmed }, fact)
    setConfirmed((earlier) => ({ ...earlier, ...added }))
    sendConfirmed(added)
  }

  return {
    deciding,
    others,
    fromProfile,
    changeProfileAnswer: (id: string) => {
      setChanged((earlier) => new Set([...earlier, id]))
      setReopenedId(id)
    },
    answerProps: {
      drafts: shown,
      onDraftChange: (id: string, draft: AnswerDraft) => {
        setDrafts((earlier) => ({ ...earlier, [id]: draft }))
      },
      hasAnswers: Object.keys(given).length > 0,
      isRunning: followUp.isRunning,
      onRunAgain: sendPanels,
      reopenedId,
    },
    confirm,
    tryAgain: () => {
      if (wasConfirm) sendConfirmed()
      else sendPanels()
    },
  }
}
