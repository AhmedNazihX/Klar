import { useId, useState, type JSX, type ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type {
  ClassificationResult,
  FollowUpQuestion,
  OpenQuestion,
  SettledBy,
  StepName,
} from '@/api'
import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'

import { settledByKinds } from './ambiguous'
import { longDate, longDateIn } from './dates'
import { QuestionAnswer, RunAgainButton, type AnswerProps } from './FollowUpQuestions'
import { VendorLetterDialog } from './VendorLetterDialog'

/** One thing that would settle the question, with what the user can do about it, if anything. */
function Item({
  text,
  action,
  children,
}: {
  text: ReactNode
  action?: ReactNode
  children?: ReactNode
}): JSX.Element {
  return (
    <li className="flex flex-col gap-3 border-t border-hairline py-2">
      <div className="flex min-h-12 flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <span className="min-w-0 flex-1 basis-[240px] text-[15px] leading-[1.45] text-ink">
          {text}
        </span>
        {action}
      </div>
      {children}
    </li>
  )
}

/** A question the user can answer here: Answer opens its answer control below it (P5b's loop). */
function AnswerItem({
  question,
  ...answers
}: { question: FollowUpQuestion } & AnswerProps): JSX.Element {
  const { t } = useTranslation()
  const textId = useId()
  const answerId = useId()
  const [isOpen, setIsOpen] = useState(false)
  return (
    <Item
      text={<span id={textId}>{question.text}</span>}
      action={
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={isOpen}
          aria-controls={answerId}
          onClick={() => {
            setIsOpen((previous) => !previous)
          }}
        >
          {t('ambiguous.settle.answer')}
        </Button>
      }
    >
      <div id={answerId} hidden={!isOpen} className="flex flex-col gap-2">
        {question.hint && <p className="m-0 text-body-small text-slate">{question.hint}</p>}
        <QuestionAnswer question={question} labelledBy={textId} {...answers} />
      </div>
    </Item>
  )
}

/** The guidance a question waits for, in the screen's language: on the high-risk check, the
 *  Commission's high-risk guidelines (the only guidance it names, E12), dated as the engine dated
 *  them; anywhere else, or with no date found, the engine's own words. */
function guidanceText(t: TFunction, language: Language, item: SettledBy, step: StepName): string {
  const date = step === 'high_risk' ? longDateIn(item.text) : null
  if (date === null) return item.text
  return t('ambiguous.settledBy.guidance', { date: longDate(date, language) })
}

/**
 * "What would settle it" (artboard `ResultAmbiguous`, decision 026 items 3 and 4): the questions
 * the user can answer here, which run the checks again (P5b); what the vendor can say, with Draft
 * a request (P28's letter), unless the user is the provider; and the guidance the question waits
 * for, named as it stands, as a plain item: Klar promises no re-check when it is final. The two
 * kinds of settled_by are fixed (E12), so their words come from the screen's language.
 */
export function SettleIt({
  question,
  step,
  result,
  toolId,
  toolName,
  questions,
  runCount,
  answers,
}: {
  question: OpenQuestion
  /** The step that left the question open. */
  step: StepName
  result: ClassificationResult
  toolId: string
  /** The tool's name, which the request names. */
  toolName: string | null
  /** The result's follow-up questions whose answer bears on the open point. */
  questions: readonly FollowUpQuestion[]
  /** Puts the screen's run action here, for that many questions. */
  runCount?: number
  answers: AnswerProps
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  const [isLetterOpen, setIsLetterOpen] = useState(false)
  const { provider, guidance } = settledByKinds(question)
  const canAskVendor = result.role !== 'provider'
  const requestButton = (
    <Button
      variant="ghost"
      size="sm"
      aria-haspopup="dialog"
      onClick={() => {
        setIsLetterOpen(true)
      }}
    >
      {t('ambiguous.settle.draftRequest')}
    </Button>
  )
  // The vendor's side: the provider's own assessment when the question names it, otherwise how
  // the vendor reads the point; a provider is the vendor, so it gets no request.
  const vendorItems =
    provider.length > 0
      ? provider.map((item) => (
          <Item
            key={item.text}
            text={t('ambiguous.settledBy.provider')}
            action={canAskVendor && requestButton}
          />
        ))
      : canAskVendor && <Item text={t('ambiguous.settle.vendorReading')} action={requestButton} />
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-1 flex-col gap-1 px-7 py-6"
    >
      <h2 id={headingId} className="m-0 mb-2.5 text-heading-panel text-ink">
        {t('ambiguous.settle.heading')}
      </h2>
      <ul className="m-0 flex list-none flex-col p-0">
        {questions.map((asked) => (
          <AnswerItem key={asked.id} question={asked} {...answers} />
        ))}
        {vendorItems}
        {guidance.map((item) => (
          <Item key={item.text} text={guidanceText(t, language, item, step)} />
        ))}
      </ul>
      {runCount !== undefined && (
        <div className="mt-2">
          <RunAgainButton count={runCount} {...answers} />
        </div>
      )}
      {canAskVendor && (
        <VendorLetterDialog
          isOpen={isLetterOpen}
          onClose={() => {
            setIsLetterOpen(false)
          }}
          toolId={toolId}
          toolName={toolName}
          result={result}
          kind="request"
        />
      )}
    </GlassPanel>
  )
}
