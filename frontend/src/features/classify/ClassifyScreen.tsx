import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import { ScreenTitle } from '@/components/ScreenTitle'
import { ClassifyRunError, useClassify } from '@/hooks/use-classify'
import { useLanguage } from '@/hooks/use-language'

import {
  classificationRunOptions,
  clearDraft,
  readDraft,
  saveDraft,
  type ClassificationRun,
} from './classification-store'
import { DescriptionForm } from './DescriptionForm'
import { DescriptionFormSchema, type DescriptionFormValues } from './description-form'
import { ProgressPanel } from './ProgressPanel'

/**
 * Describe a tool (artboards `Classify`, `ClassifyError`): the description form beside the live
 * check list. A finished run opens its result; a run that stops keeps the description and shows
 * where and why. Runs start only when the user asks: each one is a paid model run. Try again
 * and Save for later take what the form holds now, edits since the last run included.
 */
export function ClassifyScreen(): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { progress, run } = useClassify()
  // useForm takes its defaults on mount only (the saved draft); the form owns the values after.
  const form = useForm<DescriptionFormValues>({
    resolver: zodResolver(DescriptionFormSchema),
    defaultValues: readDraft(),
  })

  function start(values: DescriptionFormValues): void {
    saveDraft(values)
    run.mutate(
      // The original text is only a view of the dates (decision 020): runs stay on the amended text.
      { description: values.description, language },
      {
        onSuccess: (result) => {
          const toolId = crypto.randomUUID()
          const saved: ClassificationRun = {
            toolId,
            name: values.name,
            description: values.description,
            result,
          }
          queryClient.setQueryData(classificationRunOptions(toolId).queryKey, saved)
          clearDraft()
          // The app frame keeps the law version in the address across links.
          void navigate({ to: '/app/inventory/$toolId', params: { toolId } })
        },
      },
    )
  }

  const submit = form.handleSubmit(start)
  const failure = run.error instanceof ClassifyRunError ? run.error.failure : null
  return (
    <>
      <div className="flex max-w-[760px] flex-col gap-1.5">
        <ScreenTitle>{t('classify.title')}</ScreenTitle>
        <p className="m-0 text-body text-slate">{t('classify.subtitle')}</p>
      </div>
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        <div className="min-w-0 flex-1">
          <DescriptionForm form={form} isRunning={run.isPending} onSubmit={submit} />
        </div>
        <ProgressPanel
          progress={progress}
          isRunning={run.isPending}
          failure={run.isError ? (failure ?? { kind: 'network' }) : null}
          onTryAgain={() => void submit()}
          onSaveForLater={() => {
            saveDraft(form.getValues())
            void navigate({ to: '/app/inventory' })
          }}
        />
      </div>
    </>
  )
}
