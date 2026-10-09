import type { SupabaseClient } from '@supabase/supabase-js'
import { z } from 'zod'

// The duties a user ticked off, per tool (story P24 on P19's duty_progress table, owner-only RLS).
// A tick is a row: ticking inserts it, unticking deletes it; a tick is never edited. The database
// stamps when it was ticked (created_at).

/** One ticked duty: the tool and the obligations table's key for the duty. */
export type DutyTick = { toolId: string; obligationKey: string }

const TickRowSchema = z.object({
  system_id: z.uuid(),
  obligation_key: z.string(),
})

/** Every duty the user has ticked off, on every tool. */
export async function fetchDutyTicks(client: SupabaseClient): Promise<DutyTick[]> {
  const ticks = await client
    .from('duty_progress')
    .select('system_id, obligation_key')
    .order('created_at', { ascending: true })
  if (ticks.error) throw ticks.error
  return z
    .array(TickRowSchema)
    .parse(ticks.data)
    .map((row) => ({ toolId: row.system_id, obligationKey: row.obligation_key }))
}

/** Ticks the duty off for the tool. */
export async function addDutyTick(client: SupabaseClient, tick: DutyTick): Promise<void> {
  const added = await client
    .from('duty_progress')
    .insert({ system_id: tick.toolId, obligation_key: tick.obligationKey })
  if (added.error) throw added.error
}

/** Clears the duty's tick for the tool. */
export async function removeDutyTick(client: SupabaseClient, tick: DutyTick): Promise<void> {
  const removed = await client
    .from('duty_progress')
    .delete()
    .eq('system_id', tick.toolId)
    .eq('obligation_key', tick.obligationKey)
  if (removed.error) throw removed.error
}
