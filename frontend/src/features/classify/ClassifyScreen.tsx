import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState, type JSX } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { ScreenTitle } from '@/components/ScreenTitle'
import { ClassifyRunError, useClassify } from '@/hooks/use-classify'
import { useLanguage } from '@/hooks/use-language'
import { useSaveClassifiedTool } from '@/hooks/use-save-classified-tool'
import { classifyWriteFailure } from '@/lib/company-profile'

import {
  clearDraft,
  putRun,
  readDraft,
  saveDraft,
  type ClassificationRun,
} from './classification-store'
import { DescriptionForm } from './DescriptionForm'
import { DescriptionFormSchema, type DescriptionFormValues } from './description-form'
import { ProgressPanel } from './ProgressPanel'

/**
 * Describe a tool (artboards `Classify`, `ClassifyError`): the description form beside the live
 * check list. A finished run is added to the inventory (P6): as a new tool, or as the next run of
 * the tool "Classify this tool" came from. It then opens its result;
 * a run that stops keeps the description and shows where and why. Runs start only when the user
 * asks: each one is a paid model run. Try again and Save for later take what the form holds now,
 * edits since the last run included.
 */
export function ClassifyScreen(): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { progress, run } = useClassify()
  const save = useSaveClassifiedTool()
  // The draft is read on mount only: useForm takes its values as defaults and owns them after;
  // its tool (after "Classify this tool") is where the run is saved.
  const [{ values: draftValues, toolId: draftToolId }] = useState(readDraft)
  const form = useForm<DescriptionFormValues>({
    resolver: zodResolver(DescriptionFormSchema),
    defaultValues: draftValues,
  })

  /** Adds the finished run to the inventory (on the draft's tool, else as a new tool), then opens
   *  its result. A run that can't be saved still opens (it was paid for), under a local id and
   *  with a note that it wasn't saved. */
  async function keep(values: DescriptionFormValues, result: ClassificationResult): Promise<void> {
    // An unnamed tool stays unnamed: the screens show "Your tool" in the reader's language.
    const name = values.name === '' ? null : values.name
    let savedId: string | null = null
    let saveFailure: ClassificationRun['saveFailure']
    try {
      savedId = await save.mutateAsync({
        toolId: draftToolId,
        name,
        description: values.description,
        result,
        inventoryName: t('welcome.inventoryName'),
      })
    } catch (error) {
      saveFailure =
        classifyWriteFailure(error, 'save') === 'storage-full' ? 'storage-full' : 'failed'
    }
    const toolId = savedId ?? crypto.randomUUID()
    putRun(queryClient, { toolId, name, description: values.description, result, saveFailure })
    clearDraft()
    // The app frame keeps the law version in the address across links.
    void navigate({ to: '/app/inventory/$toolId', params: { toolId } })
  }

  function start(values: DescriptionFormValues): void {
    saveDraft(values, draftToolId)
    run.mutate(
      // The original text is only a view of the dates (decision 020): runs stay on the amended text.
      { description: values.description, language },
      { onSuccess: (result) => void keep(values, result) },
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
          {/* Busy until the run is saved too, so a second click can't start another paid run. */}
          <DescriptionForm
            form={form}
            isRunning={run.isPending || save.isPending}
            onSubmit={submit}
          />
        </div>
        <ProgressPanel
          progress={progress}
          isRunning={run.isPending}
          failure={run.isError ? (failure ?? { kind: 'network' }) : null}
          onTryAgain={() => void submit()}
          onSaveForLater={() => {
            saveDraft(form.getValues(), draftToolId)
            void navigate({ to: '/app/inventory' })
          }}
        />
      </div>
    </>
  )
}
