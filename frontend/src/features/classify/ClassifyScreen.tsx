import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

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
import type { DescriptionFormValues } from './description-form'
import { ProgressPanel } from './ProgressPanel'

/**
 * Describe a tool (artboards `Classify`, `ClassifyError`): the description form beside the live
 * check list. A finished run opens its result; a run that stops keeps the description and shows
 * where and why. Runs start only when the user asks: each one is a paid model run.
 */
export function ClassifyScreen(): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { progress, run } = useClassify()
  // The draft is read once: the form owns the values from then on.
  const [draft] = useState(readDraft)
  const [lastValues, setLastValues] = useState<DescriptionFormValues | null>(null)

  function start(values: DescriptionFormValues): void {
    saveDraft(values)
    setLastValues(values)
    run.mutate(
      // The original text is only a view of the dates (decision 020): runs stay on the amended text.
      { description: values.description, language },
      {
        onSuccess: (result) => {
          const toolId = crypto.randomUUID()
          const saved: ClassificationRun = {
            toolId,
            name: values.name || t('classify.untitled'),
            description: values.description,
            language,
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

  const failure = run.error instanceof ClassifyRunError ? run.error.failure : null
  return (
    <>
      <div className="flex max-w-[760px] flex-col gap-1.5">
        <h1 className="m-0 text-[30px] leading-tight font-semibold tracking-[-0.03em] text-ink md:text-heading-page">
          {t('classify.title')}
        </h1>
        <p className="m-0 text-body text-slate">{t('classify.subtitle')}</p>
      </div>
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        <div className="min-w-0 flex-1">
          <DescriptionForm defaultValues={draft} isRunning={run.isPending} onSubmit={start} />
        </div>
        <ProgressPanel
          progress={progress}
          isRunning={run.isPending}
          failure={run.isError ? (failure ?? { kind: 'network' }) : null}
          onTryAgain={() => {
            if (lastValues) start(lastValues)
          }}
          onSaveForLater={() => void navigate({ to: '/app/inventory' })}
        />
      </div>
    </>
  )
}
