import { useId, type BaseSyntheticEvent, type JSX } from 'react'
import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import { cn } from '@/lib/utils'

import { errorKey, type DescriptionFormValues } from './description-form'
import { PersonalDataNotice } from './PersonalDataNotice'

const TIP_KEYS = ['decides', 'affects', 'origin', 'changes'] as const

const FIELD_CLASS =
  'w-full rounded-[18px] border border-border bg-white/72 px-4.5 py-3 text-body text-ink shadow-[inset_0_2px_6px_rgb(15_27_45/0.06)] placeholder:text-slate/80'

function FieldError({
  id,
  message,
}: {
  id: string
  message: string | undefined
}): JSX.Element | null {
  const { t } = useTranslation()
  const key = errorKey(message)
  if (!key) return null
  return (
    <p id={id} className="m-0 text-caption text-risk-prohibited">
      {t(key)}
    </p>
  )
}

export type DescriptionFormProps = {
  /** The screen owns the form, so Try again and Save for later read what is in it now. */
  form: UseFormReturn<DescriptionFormValues>
  isRunning: boolean
  /** The form's validated submit (`form.handleSubmit(…)`). */
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  /** False while Klar asks for more of the description (artboard `ClassifyVague`): the prompts
   *  below carry Run the checks instead. */
  hasRunAction?: boolean
  /** The text "Edit description" opened with left answers out to fit the limit: a note under the
   *  description says so. */
  hasDroppedAnswers?: boolean
}

/**
 * Where the user describes the tool in their own words (artboard `Classify`): a name, the
 * description with the personal-data warning, the four things worth mentioning and the privacy
 * line, the language Klar answers in, and Run the checks.
 */
export function DescriptionForm({
  form,
  isRunning,
  onSubmit,
  hasRunAction = true,
  hasDroppedAnswers = false,
}: DescriptionFormProps): JSX.Element {
  const { t } = useTranslation()
  const nameId = useId()
  const descriptionId = useId()
  const nameErrorId = useId()
  const descriptionErrorId = useId()
  const tipsId = useId()
  const droppedId = useId()
  const { errors } = form.formState
  const descriptionNotes = [
    tipsId,
    ...(hasDroppedAnswers ? [droppedId] : []),
    ...(errors.description ? [descriptionErrorId] : []),
  ].join(' ')

  return (
    <GlassPanel as="section" className="flex min-w-0 flex-col gap-4 p-6">
      <form noValidate onSubmit={(event) => void onSubmit(event)} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label htmlFor={nameId} className="text-body-small font-semibold text-ink">
            {t('classify.nameLabel')}
          </label>
          <input
            id={nameId}
            type="text"
            autoComplete="off"
            placeholder={t('classify.namePlaceholder')}
            aria-invalid={errors.name ? true : undefined}
            aria-describedby={errors.name ? nameErrorId : undefined}
            className={cn(FIELD_CLASS, 'h-12 rounded-pill py-0')}
            {...form.register('name')}
          />
          <FieldError id={nameErrorId} message={errors.name?.message} />
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor={descriptionId} className="text-body-small font-semibold text-ink">
            {t('classify.descriptionLabel')}
          </label>
          <textarea
            id={descriptionId}
            rows={6}
            aria-invalid={errors.description ? true : undefined}
            aria-describedby={descriptionNotes}
            className={cn(FIELD_CLASS, 'min-h-[150px] resize-y py-4 text-[17px]')}
            {...form.register('description')}
          />
          {hasDroppedAnswers && (
            <p id={droppedId} className="m-0 text-caption font-normal text-ink-2">
              {t('classify.answersDropped')}
            </p>
          )}
          <FieldError id={descriptionErrorId} message={errors.description?.message} />
          <PersonalDataNotice control={form.control} />
        </div>
        <div id={tipsId} className="flex flex-wrap items-center gap-2">
          <span className="text-caption font-normal text-slate">{t('classify.tipsLabel')}</span>
          {TIP_KEYS.map((key) => (
            <span
              key={key}
              className="rounded-pill px-2.5 py-1 text-caption font-normal text-ink glass-thin"
            >
              {t(`classify.tips.${key}`)}
            </span>
          ))}
        </div>
        <p className="m-0 flex items-start gap-2 text-caption font-normal text-ink-2">
          <Icon name="privacy" size={16} className="mt-px" />
          <span>{t('classify.privacy')}</span>
        </p>
        {hasRunAction && (
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <span className="text-caption font-normal text-slate">{t('classify.language')}</span>
            <Button type="submit" disabled={isRunning}>
              {isRunning ? t('classify.running') : t('classify.run')}
            </Button>
          </div>
        )}
      </form>
    </GlassPanel>
  )
}
