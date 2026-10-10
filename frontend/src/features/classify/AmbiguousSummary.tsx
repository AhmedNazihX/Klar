import type { JSX, ReactNode } from 'react'

import type { FollowUpQuestion } from '@/api'

import type { OpenPoint } from './ambiguous'
import { AmbiguousVerdict } from './AmbiguousVerdict'
import type { ClassificationRun } from './classification-store'
import type { AnswerProps } from './FollowUpQuestions'
import { ReadingCards } from './ReadingCards'
import { SettleIt } from './SettleIt'
import { TakeItToALawyer } from './TakeItToALawyer'

/** The summary of a legally ambiguous result (artboard `ResultAmbiguous`), under the result's
 *  title row: the verdict with the open point and the date duties would apply from; both
 *  readings, the applied one marked; what would settle it beside taking it to a lawyer. Returns a
 *  fragment, so its panels stay the screen's direct children (load motion). */
export function AmbiguousSummary({
  run,
  point,
  note,
  questions,
  runCount,
  answers,
  onOpenReviewer,
}: {
  run: ClassificationRun
  /** The open question and the step that left it open. */
  point: OpenPoint
  /** Under the verdict: what the original text's run found, and a re-run's progress. */
  note?: ReactNode
  /** The result's follow-up questions whose answer bears on the open point (P5b). */
  questions: readonly FollowUpQuestion[]
  /** Puts the screen's run action under what would settle it, for that many questions; left
   *  out when another panel of questions follows and holds it. */
  runCount?: number
  answers: AnswerProps
  /** Opens the reviewer view. */
  onOpenReviewer: () => void
}): JSX.Element {
  const { result } = run
  return (
    <>
      <AmbiguousVerdict result={result} question={point.question} today={new Date()} />
      {note}
      <ReadingCards question={point.question} step={point.step} result={result} />
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row">
        <SettleIt
          question={point.question}
          step={point.step}
          result={result}
          toolId={run.toolId}
          toolName={run.name}
          questions={questions}
          runCount={runCount}
          answers={answers}
        />
        <TakeItToALawyer run={run} onOpenReviewer={onOpenReviewer} />
      </div>
    </>
  )
}
