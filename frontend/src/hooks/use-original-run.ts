import { skipToken, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'
import {
  classificationRunKey,
  type ClassificationRun,
} from '@/features/classify/classification-store'

import { heldSessionId } from './use-anonymous-session'
import { ClassifyRunError, useClassify, type ClassifyFailure } from './use-classify'
import { useLanguage } from './use-language'

/** The original-text run of `run`'s description and answers, under the runs' key (a sign-out
 *  forgets it with them). Keyed by what was checked and on which date, so a later run of the tool
 *  (another answer included) gets its own. */
export function originalRunKey(run: ClassificationRun) {
  return [
    ...classificationRunKey,
    run.toolId,
    'original',
    run.description,
    run.answers ?? {},
    run.result.as_of,
  ] as const
}

export type OriginalRun = {
  /** The result under the original 2024 text, once the user has had it checked. */
  result: ClassificationResult | undefined
  /** Runs the checks under the original text: a paid run, so only when the user asks. */
  start: () => void
  isRunning: boolean
  failure: ClassifyFailure | null
}

/** The original-text result of `run`, if the user has had it checked in this tab. Never fetches:
 *  only `useOriginalRun`'s `start` fills it. */
export function useOriginalResult(run: ClassificationRun): ClassificationResult | undefined {
  return useQuery<ClassificationResult>({
    queryKey: originalRunKey(run),
    queryFn: skipToken,
    staleTime: Infinity,
    gcTime: Infinity,
  }).data
}

/**
 * The same description checked under the original 2024 text, to compare with the tool's result
 * (decision 020: class and route come from the engine's original-text run). It is kept for this
 * tab only and never saved to the inventory: the tool's result stays the amended text's. It runs
 * on the amended run's date, so the two read the law on the same day.
 */
export function useOriginalRun(run: ClassificationRun): OriginalRun {
  const queryClient = useQueryClient()
  const language = useLanguage()
  const { run: classify } = useClassify()
  const result = useOriginalResult(run)

  function start(): void {
    const session = heldSessionId(queryClient)
    classify.mutate(
      {
        description: run.description,
        // The follow-up answers the tool's run used, so both texts read the same facts (P5b).
        ...(run.answers && { answers: run.answers }),
        language,
        law_version: 'original',
        as_of: run.result.as_of,
      },
      {
        onSuccess: (checked) => {
          // A sign-out or Delete my data (here or in another tab) while the run streamed forgot
          // the session's runs: this one belongs to that session and isn't kept either.
          if (session !== null && heldSessionId(queryClient) !== session) return
          queryClient.setQueryData(originalRunKey(run), checked)
        },
      },
    )
  }

  let failure: ClassifyFailure | null = null
  if (classify.isError) {
    failure =
      classify.error instanceof ClassifyRunError ? classify.error.failure : { kind: 'network' }
  }
  return { result, start, isRunning: classify.isPending, failure }
}
