import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { FollowUpQuestion } from '@/api'
import { Button } from '@/components/Button'
import { FactQuestion } from '@/components/FactQuestion'
import { GlassPanel } from '@/components/GlassPanel'

import type { AnswerDraft, AnswerDrafts } from './follow-up-answers'
import { QuestionAnswer } from './FollowUpQuestions'

export type DescriptionPromptsProps = {
  /** The engine's three prompts (what it decides, who it affects, bought or built), each with
   *  its example line as the hint. */
  questions: readonly FollowUpQuestion[]
  drafts: AnswerDrafts
  onDraftChange: (id: string, draft: AnswerDraft) => void
  /** Whether there is anything new to run on: an answer, or a changed description. */
  canRun: boolean
  isRunning: boolean
  onRun: () => void
}

/**
 * "Klar needs a little more to start" (artboard `ClassifyVague`, decision 026 item 10): the
 * description was too thin for the checks to start, so the screen asks the engine's three prompts
 * in place of the fact questions. Run the checks runs again with the answers appended to the
 * description (decision 019); until something is added, there is nothing new to run.
 */
export function DescriptionPrompts({
  questions,
  drafts,
  onDraftChange,
  canRun,
  isRunning,
  onRun,
}: DescriptionPromptsProps): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-4 p-6 shadow-[0_0_0_2px_rgb(45_75_224/0.25),0_22px_50px_-20px_rgb(45_75_224/0.3)]"
    >
      <div className="flex flex-col gap-1.5">
        <h2 id={headingId} className="m-0 text-heading-small text-ink">
          {t('classify.prompts.title')}
        </h2>
        <p className="m-0 text-body-small text-slate">{t('classify.prompts.intro')}</p>
      </div>
      <div className="flex flex-col gap-2.5">
        {questions.map((question) => (
          <FactQuestion
            key={question.id}
            question={question.text}
            hint={question.hint}
            renderAnswer={(labelledBy) => (
              <QuestionAnswer
                question={question}
                labelledBy={labelledBy}
                drafts={drafts}
                onDraftChange={onDraftChange}
                isRunning={isRunning}
              />
            )}
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <span className="text-caption font-normal text-slate">{t('classify.prompts.footer')}</span>
        <Button disabled={!canRun || isRunning} onClick={onRun}>
          {isRunning ? t('classify.running') : t('classify.run')}
        </Button>
      </div>
    </GlassPanel>
  )
}
