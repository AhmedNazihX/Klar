import { useId, type JSX, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

export type FactQuestionOption<T extends string> = { value: T; label: ReactNode }

export type AnswerChoiceProps<T extends string> = {
  /** The id of the element that names the choice (the question). */
  labelledBy: string
  /** Yes, No and Not sure for a yes/no question; empty for a question answered in words. */
  options: readonly FactQuestionOption<T>[]
  value?: T
  onChange: (value: T) => void
  /** The words field, for a question without options. */
  text?: string
  onTextChange?: (text: string) => void
  /** The words field's character limit. */
  maxLength?: number
  disabled?: boolean
}

/** The answer part of a question: one of its options (pressed, never preselected unless given),
 *  or a field for an answer in words. */
export function AnswerChoice<T extends string>({
  labelledBy,
  options,
  value,
  onChange,
  text = '',
  onTextChange,
  maxLength,
  disabled = false,
}: AnswerChoiceProps<T>): JSX.Element {
  if (options.length === 0) {
    return (
      <textarea
        aria-labelledby={labelledBy}
        value={text}
        maxLength={maxLength}
        disabled={disabled}
        rows={2}
        onChange={(event) => onTextChange?.(event.target.value)}
        className="w-full resize-y rounded-field border border-white/70 bg-white/55 px-3 py-2 text-body-small text-ink focus-visible:outline-2 focus-visible:outline-lens-blue disabled:opacity-50"
      />
    )
  }
  return (
    <div role="group" aria-labelledby={labelledBy} className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          disabled={disabled}
          onClick={() => {
            onChange(option.value)
          }}
          className={cn(
            'h-[34px] shrink-0 cursor-pointer rounded-pill border border-white/70 bg-white/45 px-3.5 text-[13px] leading-none font-medium whitespace-nowrap text-ink transition-colors hover:bg-white/62 focus-visible:outline-2 focus-visible:outline-lens-blue disabled:pointer-events-none disabled:opacity-50',
            'aria-pressed:border-lens-blue aria-pressed:bg-white aria-pressed:font-semibold aria-pressed:shadow-[0_0_0_1.5px_rgb(45_75_224/0.28)]',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export type FactQuestionProps = {
  question: ReactNode
  /** Why it matters, with the provision: "If yes, you become the provider. Art. 25(1)(a)". */
  hint?: ReactNode
  /** The answer control (usually an AnswerChoice), named by the question's element id. */
  renderAnswer: (labelledBy: string) => ReactNode
}

/** A fact Klar had to assume, asked back in plain words with Yes, No and Not sure (or answered in
 *  words), and a line on why it matters. Stack several under "Please confirm N facts". */
export function FactQuestion({ question, hint, renderAnswer }: FactQuestionProps): JSX.Element {
  const questionId = useId()
  return (
    <div className="flex flex-col gap-2 rounded-card-small px-4 py-3.5 glass-thin">
      <p id={questionId} className="m-0 text-body-small font-semibold text-ink">
        {question}
      </p>
      {hint && <p className="m-0 text-caption font-normal text-slate">{hint}</p>}
      {renderAnswer(questionId)}
    </div>
  )
}
