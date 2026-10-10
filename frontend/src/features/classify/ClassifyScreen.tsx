import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState, type JSX } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, ClassifyRequest, FollowUpQuestion } from '@/api'
import { ScreenTitle } from '@/components/ScreenTitle'
import { Button } from '@/components/ui/button'
import {
  ClassifyRunError,
  classifyFailureOf,
  saveFailureOf,
  useClassify,
} from '@/hooks/use-classify'
import { useLanguage } from '@/hooks/use-language'
import { useSaveClassifiedTool, type SavedRun } from '@/hooks/use-save-classified-tool'

import {
  clearDraft,
  putRun,
  readDraft,
  saveDraft,
  type ClassificationRun,
  type DraftTool,
} from './classification-store'
import { DescriptionForm } from './DescriptionForm'
import { DescriptionFormSchema, type DescriptionFormValues } from './description-form'
import { DescriptionPrompts } from './DescriptionPrompts'
import { answersOf, withAnswers, type AnswerDraft, type AnswerDrafts } from './follow-up-answers'
import { ProgressPanel } from './ProgressPanel'
import { toolName } from './result-text'

/** The quiet line while the draft is for a tool the user has ("Classify this tool"): the run is
 *  saved on it, as its next check, unless the user makes it a new tool instead. */
function DraftToolNote({
  tool,
  onNewTool,
}: {
  tool: DraftTool
  onNewTool: () => void
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <p className="m-0 mb-3 flex flex-wrap items-center gap-x-2 text-body-small text-slate">
      {t('classify.draftTool.note', { name: toolName(t, tool.name) })}
      <Button variant="link" size="sm" className="h-auto px-0" onClick={onNewTool}>
        {t('classify.draftTool.newTool')}
      </Button>
    </p>
  )
}

/** What a run too thin to start asked (E13): the engine's three prompts, and the description
 *  they were asked about, so Run the checks waits until something is added. */
type AskedForMore = { questions: FollowUpQuestion[]; description: string }

/** The prompts a run too thin to start asked, or null for any other outcome. */
function askedForMore(error: unknown, description: string): AskedForMore | null {
  if (!(error instanceof ClassifyRunError) || error.failure.kind !== 'needs_description') {
    return null
  }
  return { questions: error.failure.questions, description }
}

/**
 * Describe a tool (artboards `Classify`, `ClassifyError`, `ClassifyVague`): the description form
 * beside the live check list. A description too thin to start (E13) asks three prompts under the
 * form while the checks wait; their answers go with every later run, appended to the
 * description (decision 019), and a class-less run is never saved. A finished run is added to
 * the inventory (P6): as a new tool, or as the next run of the tool "Classify this tool" came
 * from. It then opens its result; a run that stops keeps the description and shows where and why. Runs start only when the user
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
  // its tool (after "Classify this tool") is where the run is saved, until the user lets it go.
  const [{ values: draftValues, tool: initialTool }] = useState(readDraft)
  const [draftTool, setDraftTool] = useState(initialTool)
  const form = useForm<DescriptionFormValues>({
    resolver: zodResolver(DescriptionFormSchema),
    defaultValues: draftValues,
  })
  const [asked, setAsked] = useState<AskedForMore | null>(null)
  const [drafts, setDrafts] = useState<AnswerDrafts>({})
  const description = useWatch({ control: form.control, name: 'description' })
  const answers = asked ? answersOf(t, asked.questions, drafts) : {}
  const hasAnswers = Object.keys(answers).length > 0

  /** Adds the finished run to the inventory (on the draft's tool, else as a new tool), then opens
   *  its result. A run that can't be saved still opens (it was paid for), under a local id and
   *  with a note that it wasn't saved. */
  async function keep(values: DescriptionFormValues, result: ClassificationResult): Promise<void> {
    // An unnamed tool stays unnamed: the screens show "Your tool" in the reader's language.
    const name = values.name === '' ? null : values.name
    let saved: SavedRun | null = null
    let saveFailure: ClassificationRun['saveFailure']
    try {
      saved = await save.mutateAsync({
        toolId: draftTool?.toolId ?? null,
        name,
        description: values.description,
        result,
        inventoryName: t('welcome.inventoryName'),
      })
    } catch (error) {
      saveFailure = saveFailureOf(error)
    }
    const toolId = saved?.toolId ?? crypto.randomUUID()
    putRun(queryClient, {
      toolId,
      name,
      description: values.description,
      result,
      saveFailure,
      // As the database numbered it: a run saved on a tool that had runs isn't run 1.
      runNo: saved?.runNo ?? undefined,
    })
    clearDraft()
    // The app frame keeps the law version in the address across links.
    void navigate({ to: '/app/inventory/$toolId', params: { toolId } })
  }

  function start(values: DescriptionFormValues): void {
    saveDraft(values, draftTool)
    // The original text is only a view of the dates (decision 020): runs stay on the amended text.
    const body: ClassifyRequest = { description: values.description, language }
    run.mutate(hasAnswers ? { ...body, answers } : body, {
      // The tool keeps the answers in its description: the run that asked for them is never saved.
      onSuccess: (result) =>
        void keep({ ...values, description: withAnswers(values.description, answers) }, result),
      onError: (error) => {
        setAsked((earlier) => askedForMore(error, values.description) ?? earlier)
      },
    })
  }

  const submit = form.handleSubmit(start)
  return (
    <>
      <div className="flex max-w-[760px] flex-col gap-1.5">
        <ScreenTitle>{t('classify.title')}</ScreenTitle>
        <p className="m-0 text-body text-slate">{t('classify.subtitle')}</p>
      </div>
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        <div className="min-w-0 flex-1">
          {draftTool && (
            <DraftToolNote
              tool={draftTool}
              onNewTool={() => {
                setDraftTool(null)
                saveDraft(form.getValues(), null)
              }}
            />
          )}
          {/* Busy until the run is saved too, so a second click can't start another paid run. */}
          <DescriptionForm
            form={form}
            isRunning={run.isPending || save.isPending}
            onSubmit={submit}
            hasRunAction={asked === null}
          />
          {asked && (
            <div className="mt-5">
              <DescriptionPrompts
                questions={asked.questions}
                drafts={drafts}
                onDraftChange={(id: string, draft: AnswerDraft) => {
                  setDrafts((earlier) => ({ ...earlier, [id]: draft }))
                }}
                canRun={hasAnswers || description.trim() !== asked.description.trim()}
                isRunning={run.isPending || save.isPending}
                onRun={() => void submit()}
              />
            </div>
          )}
        </div>
        <ProgressPanel
          progress={progress}
          isRunning={run.isPending}
          failure={classifyFailureOf(run)}
          onTryAgain={() => void submit()}
          onSaveForLater={() => {
            saveDraft(form.getValues(), draftTool)
            void navigate({ to: '/app/inventory' })
          }}
        />
      </div>
    </>
  )
}
