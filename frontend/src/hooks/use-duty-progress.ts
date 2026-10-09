import type { SupabaseClient } from '@supabase/supabase-js'
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query'

import { addDutyTick, fetchDutyTicks, removeDutyTick, type DutyTick } from '@/lib/duty-progress'
import { supabase } from '@/lib/supabase'

import { withAnonymousSession } from './use-anonymous-session'
import { myDataCountsKey } from './use-my-data-counts'
import { userDataKey } from './use-user-data-overview'

/** Under the user-data key, so an import or a delete refreshes the ticks with the rest. */
export const dutyTicksKey = [...userDataKey, 'duty-progress'] as const

/** The duties the user ticked off, read once the anonymous session exists. Disabled when
 *  Supabase is not configured. */
export function useDutyTicks(client: SupabaseClient | null = supabase): UseQueryResult<DutyTick[]> {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: dutyTicksKey,
    queryFn: async (): Promise<DutyTick[]> =>
      fetchDutyTicks(await withAnonymousSession(queryClient, client)),
    enabled: client !== null,
  })
}

export type DutyTickChange = DutyTick & {
  /** True ticks the duty off; false clears its tick. */
  isDone: boolean
}

function isSameTick(a: DutyTick, b: DutyTick): boolean {
  return a.toolId === b.toolId && a.obligationKey === b.obligationKey
}

/** The ticks as they are after `change`. */
function withChange(ticks: readonly DutyTick[], change: DutyTickChange): DutyTick[] {
  const others = ticks.filter((tick) => !isSameTick(tick, change))
  const tick = { toolId: change.toolId, obligationKey: change.obligationKey }
  return change.isDone ? [...others, tick] : others
}

/**
 * Ticks a duty off or clears it. The box changes at once; a write that fails puts the ticks back
 * as they were (the caller shows the error). The ticks and Your data's counts are read again
 * afterwards. One click is one request: nothing is retried.
 */
export function useToggleDutyTick(
  client: SupabaseClient | null = supabase,
): UseMutationResult<void, Error, DutyTickChange, { previous: DutyTick[] | undefined }> {
  const queryClient = useQueryClient()
  return useMutation({
    retry: false,
    mutationFn: async (change: DutyTickChange) => {
      const sessionClient = await withAnonymousSession(queryClient, client)
      const tick = { toolId: change.toolId, obligationKey: change.obligationKey }
      await (change.isDone ? addDutyTick(sessionClient, tick) : removeDutyTick(sessionClient, tick))
    },
    onMutate: async (change) => {
      await queryClient.cancelQueries({ queryKey: dutyTicksKey })
      const previous = queryClient.getQueryData<DutyTick[]>(dutyTicksKey)
      queryClient.setQueryData<DutyTick[]>(dutyTicksKey, (ticks = []) => withChange(ticks, change))
      return { previous }
    },
    onError: (_error, _change, context) => {
      queryClient.setQueryData(dutyTicksKey, context?.previous)
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: dutyTicksKey }),
        queryClient.invalidateQueries({ queryKey: myDataCountsKey }),
      ])
    },
  })
}
