import type { SupabaseClient } from '@supabase/supabase-js'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import type { ClassificationResult } from '@/api'
import {
  putRun,
  runNumber,
  toolResultKey,
  type ClassificationRun,
} from '@/features/classify/classification-store'
import { supabase } from '@/lib/supabase'
import { addFollowUpRun, deleteRun, type Answers, type RunRef } from '@/lib/tool-runs'

import { heldSessionId, withAnonymousSession } from './use-anonymous-session'
import { classifyFailureOf, saveFailureOf, useClassify, type ClassifyFailure } from './use-classify'
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
 *
 * A re-run or an undo belongs to the session it started under: when a sign-out or Delete my data
 * (here or in another tab) ends that session before it finishes, its outcome is dropped without a
 * word, never saved or shown (as useOriginalRun does), and nothing starts a new session for it.
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

  /** Whether the session the work started under is still the one this tab holds. */
  function isSameSession(session: string | null): boolean {
    return heldSessionId(queryClient) === session
  }

  /** Saves the re-run on the tool. A run that can't be saved still shows (it was paid for), with
   *  a note that it wasn't saved. */
  async function save(
    answers: Answers,
    result: ClassificationResult,
  ): Promise<{ ref: RunRef | null; saveFailure: ClassificationRun['saveFailure'] }> {
    if (!isSaved(run, client)) return { ref: null, saveFailure: run.saveFailure }
    setIsSaving(true)
    try {
      const sessionClient = await withAnonymousSession(queryClient, client)
      const ref = await addFollowUpRun(sessionClient, {
        toolId: run.toolId,
        description: run.description,
        answers,
        result,
      })
      return { ref, saveFailure: undefined }
    } catch (error) {
      return { ref: null, saveFailure: saveFailureOf(error) }
    } finally {
      setIsSaving(false)
    }
  }

  /** Saves the re-run, then shows it with the run before it. */
  async function keep(
    answers: Answers,
    result: ClassificationResult,
    session: string | null,
  ): Promise<void> {
    if (!isSameSession(session)) return
    // A saved tool with no session held: it ended before the run started, and its run goes too.
    if (isSaved(run, client) && session === null) return
    const { ref, saveFailure } = await save(answers, result)
    if (!isSameSession(session)) return
    putRun(queryClient, {
      toolId: run.toolId,
      name: run.name,
      description: run.description,
      result,
      saveFailure,
      runNo: ref?.runNo ?? runNumber(run) + 1,
      runId: ref?.id,
      answers,
      previous: {
        runId: run.runId,
        runNo: runNumber(run),
        result: run.result,
        answers: run.answers ?? {},
        saveFailure: run.saveFailure,
      },
    })
    void queryClient.invalidateQueries({ queryKey: userDataKey })
  }

  function rerun(answers: Answers): void {
    const session = heldSessionId(queryClient)
    classify.mutate(
      // Runs stay on the amended text (decision 020), like the first run.
      { description: run.description, language, answers },
      { onSuccess: (result) => void keep(answers, result, session) },
    )
  }

  /** Deletes the shown run from the user's data; false when it was no longer there (or its id
   *  is unknown), so the tool's runs changed elsewhere. */
  async function deleteShownRun(signedIn: SupabaseClient): Promise<boolean> {
    if (run.runId === undefined) return false
    return deleteRun(signedIn, run.runId)
  }

  const undo = useMutation({
    mutationFn: async (session: string | null): Promise<void> => {
      const previous = run.previous
      if (!previous || !isSameSession(session)) return
      if (isSaved(run, client)) {
        // Ended already: there is no session to delete the run under, and none is started for it.
        if (session === null) return
        const isDeleted = await deleteShownRun(client)
        if (!isSameSession(session)) return
        if (!isDeleted) {
          // Another tab or device changed the tool's runs: show them as they are now.
          await queryClient.invalidateQueries({
            queryKey: toolResultKey(run.toolId),
            exact: true,
          })
          void queryClient.invalidateQueries({ queryKey: userDataKey })
          return
        }
      }
      putRun(queryClient, {
        toolId: run.toolId,
        name: run.name,
        description: run.description,
        result: previous.result,
        saveFailure: previous.saveFailure,
        isStored: run.isStored,
        runNo: previous.runNo,
        runId: previous.runId,
        answers: previous.answers,
      })
      void queryClient.invalidateQueries({ queryKey: userDataKey })
    },
  })

  return {
    progress,
    rerun,
    isRunning: classify.isPending || isSaving,
    failure: classifyFailureOf(classify),
    undo: () => {
      undo.mutate(heldSessionId(queryClient))
    },
    isUndoing: undo.isPending,
    hasUndoFailed: undo.isError,
  }
}
