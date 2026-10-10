import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import type { ClassificationResult } from '@/api'
import { putRun, runNumber, type ClassificationRun } from '@/features/classify/classification-store'
import { classifyWriteFailure } from '@/lib/company-profile'
import { supabase } from '@/lib/supabase'
import { addFollowUpRun, deleteRun, type Answers } from '@/lib/tool-runs'

import { withAnonymousSession } from './use-anonymous-session'
import { ClassifyRunError, useClassify, type ClassifyFailure } from './use-classify'
import { useLanguage } from './use-language'
import { userDataKey } from './use-user-data-overview'

export type FollowUpRun = {
  /** The live check list of the re-run. */
  progress: ReturnType<typeof useClassify>['progress']
  /** Runs the checks again on the description with `answers` appended (each a paid run, so only
   *  when the user asks). */
  rerun: (answers: Answers) => void
  isRunning: boolean
  failure: ClassifyFailure | null
  /** Undo answer: the run before this one is the tool's result again (deleted from the user's
   *  data first, when it was saved there). */
  undo: () => void
  isUndoing: boolean
  hasUndoFailed: boolean
}

/** Whether the tool's runs live in the user's data: a run that couldn't be saved (or an app
 *  without Supabase) lives only in this tab, and so do the runs after it. */
function isSaved(run: ClassificationRun, client: SupabaseClient | null): client is SupabaseClient {
  return client !== null && run.saveFailure === undefined
}

/**
 * The follow-up loop on a tool's result (story P5b, decision 019): the user's answers go to the
 * engine with the description it already has, and the new result becomes the tool's next run,
 * saved with the answers it used (P19's `inputs`) and shown in place with the run before it, so
 * the screen can say what changed and Undo answer can bring it back.
 */
export function useFollowUpRun(
  run: ClassificationRun,
  client: SupabaseClient | null = supabase,
): FollowUpRun {
  const queryClient = useQueryClient()
  const language = useLanguage()
  const { progress, run: classify } = useClassify()
  // Busy until the re-run is saved too, so a second click can't start another paid run.
  const [isSaving, setIsSaving] = useState(false)

  /** Saves the re-run on the tool, then shows it. A run that can't be saved still shows (it was
   *  paid for), with a note that it wasn't saved. */
  async function keep(answers: Answers, result: ClassificationResult): Promise<void> {
    let runNo = runNumber(run) + 1
    let saveFailure = run.saveFailure
    if (isSaved(run, client)) {
      setIsSaving(true)
      try {
        const sessionClient = await withAnonymousSession(queryClient, client)
        runNo = await addFollowUpRun(sessionClient, {
          toolId: run.toolId,
          description: run.description,
          answers,
          result,
        })
      } catch (error) {
        saveFailure =
          classifyWriteFailure(error, 'save') === 'storage-full' ? 'storage-full' : 'failed'
      } finally {
        setIsSaving(false)
      }
    }
    putRun(queryClient, {
      toolId: run.toolId,
      name: run.name,
      description: run.description,
      result,
      saveFailure,
      runNo,
      answers,
      previous: {
        runNo: runNumber(run),
        result: run.result,
        answers: run.answers ?? {},
        saveFailure: run.saveFailure,
      },
    })
    void queryClient.invalidateQueries({ queryKey: userDataKey })
  }

  function rerun(answers: Answers): void {
    classify.mutate(
      // Runs stay on the amended text (decision 020), like the first run.
      { description: run.description, language, answers },
      { onSuccess: (result) => void keep(answers, result) },
    )
  }

  const undo = useMutation({
    mutationFn: async (): Promise<void> => {
      const previous = run.previous
      if (!previous) return
      if (isSaved(run, client)) {
        const sessionClient = await withAnonymousSession(queryClient, client)
        await deleteRun(sessionClient, run.toolId, runNumber(run))
      }
      putRun(queryClient, {
        toolId: run.toolId,
        name: run.name,
        description: run.description,
        result: previous.result,
        saveFailure: previous.saveFailure,
        isStored: run.isStored,
        runNo: previous.runNo,
        answers: previous.answers,
      })
      void queryClient.invalidateQueries({ queryKey: userDataKey })
    },
  })

  let failure: ClassifyFailure | null = null
  if (classify.isError) {
    failure =
      classify.error instanceof ClassifyRunError ? classify.error.failure : { kind: 'network' }
  }
  return {
    progress,
    rerun,
    isRunning: classify.isPending || isSaving,
    failure,
    undo: () => {
      undo.mutate()
    },
    isUndoing: undo.isPending,
    hasUndoFailed: undo.isError,
  }
}
