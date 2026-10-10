import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { AnswerOption, FollowUpQuestion } from '@/api'
import { Button } from '@/components/Button'
import { AnswerChoice, FactQuestion } from '@/components/FactQuestion'
import { GlassPanel } from '@/components/GlassPanel'

import {
  MAX_ANSWER_CHARS,
  optionsOf,
  type AnswerDraft,
  type AnswerDrafts,
} from './follow-up-answers'

/** What a question panel needs to take answers and run the checks again. */
export type AnswerProps = {
  drafts: AnswerDrafts
  onDraftChange: (id: string, draft: AnswerDraft) => void
  /** Whether anything given so far would be sent (Not sure and blank words aren't). */
  hasAnswers: boolean
  isRunning: boolean
  onRunAgain: () => void
}

/** A question's answer control (its options, or a field for words) with the draft it holds. */
export function QuestionAnswer({
  question,
  labelledBy,
  drafts,
  onDraftChange,
  isRunning,
}: { question: FollowUpQuestion; labelledBy: string } & Pick<
  AnswerProps,
  'drafts' | 'onDraftChange' | 'isRunning'
>): JSX.Element {
  const { t } = useTranslation()
  const draft = drafts[question.id]
  return (
    <AnswerChoice<AnswerOption>
      labelledBy={labelledBy}
      options={optionsOf(question).map((value) => ({
        value,
        label: t(`followUp.option.${value}`),
      }))}
      value={draft?.option}
      onChange={(option) => {
        onDraftChange(question.id, { option })
      }}
      text={draft?.text}
      onTextChange={(text) => {
        onDraftChange(question.id, { text })
      }}
      maxLength={MAX_ANSWER_CHARS}
      disabled={isRunning}
    />
  )
}

/** "Add answers and run again": the screen's one run action, under the last question panel,
 *  for every question asked (`count`); enabled once an answer would be sent. Its label wraps on
 *  a narrow screen (the German one is long) rather than push the page sideways. */
export function RunAgainButton({
  count,
  hasAnswers,
  isRunning,
  onRunAgain,
}: { count: number } & Pick<AnswerProps, 'hasAnswers' | 'isRunning' | 'onRunAgain'>): JSX.Element {
  const { t } = useTranslation()
  return (
    <Button
      className="h-auto min-h-11 max-w-full shrink self-start py-3 text-center leading-snug whitespace-normal"
      disabled={!hasAnswers || isRunning}
      onClick={onRunAgain}
    >
      {t('followUp.runAgain', { count })}
    </Button>
  )
}

/**
 * "N open questions" (artboard `Classify`, components.md FactQuestion): what Klar couldn't settle
 * from the description, asked with Yes, No and Not sure (or in words), each with why it matters.
 * Answering runs the checks again with the answers appended to the description (decision 019).
 * The Art. 111(2) follow-ups come here too (decision 026 item 24); an assumed fact doesn't: its
 * card's Confirm answers it. `runCount` puts the screen's run action here, for that many
 * questions.
 */
export function FollowUpQuestions({
  questions,
  runCount,
  ...answers
}: {
  questions: readonly FollowUpQuestion[]
  runCount?: number
} & AnswerProps): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id={headingId} className="m-0 text-heading-panel text-ink">
          {t('followUp.heading', { count: questions.length })}
        </h2>
        <p className="m-0 text-body-small text-slate">{t('followUp.intro')}</p>
      </div>
      <div className="flex flex-col gap-2.5">
        {questions.map((question) => (
          <ConfirmQuestion key={question.id} question={question} {...answers} />
        ))}
      </div>
      {runCount !== undefined && <RunAgainButton count={runCount} {...answers} />}
    </GlassPanel>
  )
}

function ConfirmQuestion({
  question,
  ...answers
}: { question: FollowUpQuestion } & AnswerProps): JSX.Element {
  const { t } = useTranslation()
  return (
    <FactQuestion
      question={question.text}
      hint={question.hint}
      note={answers.drafts[question.id]?.isFromProfile ? t('followUp.fromProfile') : undefined}
      renderAnswer={(labelledBy) => (
        <QuestionAnswer question={question} labelledBy={labelledBy} {...answers} />
      )}
    />
  )
}
