import { zodResolver } from '@hookform/resolvers/zod'
import { useId, type JSX } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import type { InterviewChoice, InterviewQuestion } from '@/api'
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

type FieldProps = {
  fieldId: string
  describedBy: string
  hasError: boolean
  register: ReturnType<typeof useForm<AnswerValues>>['register']
}

/** A choice question's options, as radio buttons: the answer is the picked choice's key. */
function ChoiceField({
  choices,
  register,
}: FieldProps & { choices: readonly InterviewChoice[] }): JSX.Element {
  return (
    <div className="flex flex-col gap-2">
      {choices.map((choice) => (
        <label key={choice.key} className="flex items-center gap-2.5 text-body-small text-ink">
          <input
            type="radio"
            value={choice.key}
            className="size-4 accent-lens-blue"
            {...register('answer')}
          />
          {choice.label}
        </label>
      ))}
    </div>
  )
}

function TextField({
  fieldId,
  describedBy,
  hasError,
  register,
  isLong,
}: FieldProps & { isLong: boolean }): JSX.Element {
  const shared = {
    id: fieldId,
    'aria-describedby': describedBy,
    'aria-invalid': hasError,
    ...register('answer'),
  }
  return isLong ? (
    <textarea rows={4} className={`${FIELD_CLASS} resize-y py-2.5`} {...shared} />
  ) : (
    <input type="text" className={`${FIELD_CLASS} h-11`} {...shared} />
  )
}

function hintKey(isChoice: boolean, isLong: boolean) {
  if (isChoice) return 'documents.interview.hintChoice' as const
  return isLong
    ? ('documents.interview.hintSkeleton' as const)
    : ('documents.interview.hintNotice' as const)
}

/** One question of the guided interview: the field (or a choice question's options), the
 *  hint, Skip for now and Save answer. Mount it per question (`key`), so the field starts from
 *  that question's answer. */
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
  const choices = question.choices ?? []
  const isChoice = choices.length > 0
  const hasError = form.formState.errors.answer !== undefined
  const field: FieldProps = {
    fieldId,
    describedBy: hasError ? `${hintId} ${errorId}` : hintId,
    hasError,
    register: form.register,
  }
  const submit = form.handleSubmit((values) => {
    onSave(values.answer)
  })
  const Wrapper = isChoice ? 'fieldset' : 'div'
  return (
    <form
      noValidate
      onSubmit={(event) => void submit(event)}
      className="flex flex-col gap-3 rounded-tile bg-white/70 p-4 glass-thin"
    >
      <Wrapper
        className="m-0 flex flex-col gap-3 border-0 p-0"
        aria-describedby={isChoice ? field.describedBy : undefined}
      >
        {isChoice ? (
          <legend className="mb-3 p-0 text-body-small leading-snug font-semibold text-ink">
            {question.text}
          </legend>
        ) : (
          <label htmlFor={fieldId} className="text-body-small leading-snug font-semibold text-ink">
            {question.text}
          </label>
        )}
        {isChoice ? (
          <ChoiceField {...field} choices={choices} />
        ) : (
          <TextField {...field} isLong={isLong} />
        )}
      </Wrapper>
      <p id={hintId} className="m-0 text-micro text-slate">
        {t(hintKey(isChoice, isLong))}
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
