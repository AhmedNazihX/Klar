import type { SupabaseClient } from '@supabase/supabase-js'
import {
  queryOptions,
  useMutation,
  useQueries,
  useQueryClient,
  type QueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query'

import {
  fetchInterviewAnswers,
  saveInterviewAnswer,
  withAnswer,
  type AnswersByTemplate,
  type InterviewAnswer,
} from '@/features/documents/interview-answers'
import { documentDraftsKey, interviewAnswersKey } from '@/features/documents/query-keys'
import { supabase } from '@/lib/supabase'

import { withAnonymousSession } from './use-anonymous-session'

const NO_ANSWERS: AnswersByTemplate = {}

/** One tool's answers, read once the anonymous session exists. Without Supabase (a build with no
 *  backend) there are none to read: the tool has no answers yet. */
export function interviewAnswersOptions(
  queryClient: QueryClient,
  client: SupabaseClient | null,
  toolId: string,
) {
  return queryOptions({
    queryKey: interviewAnswersKey(toolId),
    queryFn: async (): Promise<AnswersByTemplate> => {
      if (!client) return NO_ANSWERS
      return fetchInterviewAnswers(await withAnonymousSession(queryClient, client), toolId)
    },
    staleTime: Infinity,
  })
}

/** Every listed tool's answers, in the order of `toolIds`. */
export function useInterviewAnswers(
  toolIds: readonly string[],
  client: SupabaseClient | null = supabase,
): UseQueryResult<AnswersByTemplate>[] {
  const queryClient = useQueryClient()
  return useQueries({
    queries: toolIds.map((toolId) => interviewAnswersOptions(queryClient, client, toolId)),
  })
}

/** Saves one answer; once stored, the tool's answers hold it and its drafts are drawn again. */
export function useSaveInterviewAnswer(
  client: SupabaseClient | null = supabase,
): UseMutationResult<void, Error, InterviewAnswer> {
  const queryClient = useQueryClient()
  return useMutation({
    retry: false,
    mutationFn: async (saved: InterviewAnswer) => {
      await saveInterviewAnswer(await withAnonymousSession(queryClient, client), saved)
    },
    onSuccess: (_result, saved) => {
      queryClient.setQueryData(interviewAnswersKey(saved.toolId), (answers?: AnswersByTemplate) =>
        withAnswer(answers ?? NO_ANSWERS, saved),
      )
      return queryClient.invalidateQueries({ queryKey: documentDraftsKey(saved.toolId) })
    },
  })
}
