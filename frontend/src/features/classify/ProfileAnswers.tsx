import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { FollowUpQuestion } from '@/api'
import { Button } from '@/components/Button'
import { FactQuestion } from '@/components/FactQuestion'
import { GlassPanel } from '@/components/GlassPanel'

import { RunAgainButton, type AnswerProps } from './FollowUpQuestions'

/**
 * "From your company profile" (story P29, decision 026 item 2): the follow-up questions the
 * profile answers, each with its answer and Change, kept out of the open questions so the user
 * sees the profile was used. Change asks the question again as an open one. The answers are sent
 * with the others when the user runs the checks again; the profile itself never reaches the
 * engine (decision 026 item 7). No artboard draws this state, so each answer reuses FactQuestion's
 * look. `runCount` puts the screen's run action here (when this is the last question panel).
 */
export function ProfileAnswers({
  questions,
  onChange,
  runCount,
  ...answers
}: {
  questions: readonly FollowUpQuestion[]
  onChange: (id: string) => void
  runCount?: number
} & AnswerProps): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id={headingId} className="m-0 text-heading-panel text-ink">
          {t('followUp.profile.heading')}
        </h2>
        <p className="m-0 text-body-small text-slate">{t('followUp.profile.intro')}</p>
      </div>
      <div className="flex flex-col gap-2.5">
        {questions.map((question) => {
          const option = answers.drafts[question.id]?.option
          return (
            <FactQuestion
              key={question.id}
              question={question.text}
              renderAnswer={(labelledBy) => (
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="text-body-small font-semibold text-ink">
                    {option && t(`followUp.option.${option}`)}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-describedby={labelledBy}
                    disabled={answers.isRunning}
                    onClick={() => {
                      onChange(question.id)
                    }}
                  >
                    {t('followUp.profile.change')}
                  </Button>
                </div>
              )}
            />
          )
        })}
      </div>
      {runCount !== undefined && <RunAgainButton count={runCount} {...answers} />}
    </GlassPanel>
  )
}
