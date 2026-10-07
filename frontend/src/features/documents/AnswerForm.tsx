import { zodResolver } from '@hookform/resolvers/zod'
import { useId, type JSX } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import type { InterviewQuestion } from '@/api'
import { Button } from '@/components/Button'

import { MAX_ANSWER_CHARS } from './interview-answers'

const AnswerSchema = z.object({ answer: z.string().max(MAX_ANSWER_CHARS) })
type AnswerValues = z.infer<typeof AnswerSchema>

const FIELD_CLASS =
  'w-full rounded-field border border-border-subtle bg-white px-3 text-body-small text-ink placeholder:text-slate/80'

export type AnswerFormProps = {
  question: InterviewQuestion
  /** The answer given before, if any; the field starts with it. */
  given: string
  /** A skeleton's answers run longer, so they get a text area. */
  isLong: boolean
  isSaving: boolean
  onSave: (answer: string) => void
  onSkip: () => void
}

/** One question of the guided interview: the field, the hint, Skip for now and Save answer.
 *  Mount it per question (`key`), so the field starts from that question's answer. */
export function AnswerForm({
  question,
  given,
  isLong,
  isSaving,
  onSave,
  onSkip,
}: AnswerFormProps): JSX.Element {
  const { t } = useTranslation()
  const fieldId = useId()
  const hintId = useId()
  const errorId = useId()
  const form = useForm<AnswerValues>({
    resolver: zodResolver(AnswerSchema),
    defaultValues: { answer: given },
  })
  const hasError = form.formState.errors.answer !== undefined
  const describedBy = hasError ? `${hintId} ${errorId}` : hintId
  const submit = form.handleSubmit((values) => {
    onSave(values.answer)
  })
  return (
    <form
      noValidate
      onSubmit={(event) => void submit(event)}
      className="flex flex-col gap-3 rounded-tile bg-white/70 p-4 glass-thin"
    >
      <label htmlFor={fieldId} className="text-body-small leading-snug font-semibold text-ink">
        {question.text}
      </label>
      {isLong ? (
        <textarea
          id={fieldId}
          rows={4}
          aria-describedby={describedBy}
          aria-invalid={hasError}
          className={`${FIELD_CLASS} resize-y py-2.5`}
          {...form.register('answer')}
        />
      ) : (
        <input
          id={fieldId}
          type="text"
          aria-describedby={describedBy}
          aria-invalid={hasError}
          className={`${FIELD_CLASS} h-11`}
          {...form.register('answer')}
        />
      )}
      <p id={hintId} className="m-0 text-micro text-slate">
        {t(isLong ? 'documents.interview.hintSkeleton' : 'documents.interview.hintNotice')}
      </p>
      {hasError && (
        <p id={errorId} className="m-0 text-caption text-risk-prohibited">
          {t('documents.interview.tooLong')}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onSkip} disabled={isSaving}>
          {t('documents.interview.skip')}
        </Button>
        <Button type="submit" size="sm" disabled={isSaving}>
          {isSaving ? t('documents.interview.saving') : t('documents.interview.save')}
        </Button>
      </div>
    </form>
  )
}
