import type { SupabaseClient } from '@supabase/supabase-js'
import { z } from 'zod'

import type { ClassificationResult } from '@/api'

import { parseStoredResult } from './stored-result'

// The user's tools and their runs in Supabase (story P6): systems and classifications (P3, P19),
// read through the inventory_tools view (each tool with its latest run, owner-only RLS).

/** One tool in the inventory, with its latest result. */
export type InventoryTool = {
  toolId: string
  name: string
  description: string
  createdAt: string
  /** The latest run's result; null while the tool has none, or when it can't be read. */
  result: ClassificationResult | null
  /** A run exists but its stored result isn't one Klar can show (an edited or broken file). */
  hasUnreadableResult: boolean
}

const TOOL_COLUMNS = 'id, name, description, created_at, run_no, result'

const ToolRowSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  description: z.string(),
  created_at: z.string(),
  run_no: z.number().int().nullable(),
  result: z.unknown(),
})
type ToolRow = z.infer<typeof ToolRowSchema>

function toTool(row: ToolRow): InventoryTool {
  const hasRun = row.run_no !== null
  const result = hasRun ? parseStoredResult(row.result) : null
  return {
    toolId: row.id,
    name: row.name,
    description: row.description,
    createdAt: row.created_at,
    result,
    hasUnreadableResult: hasRun && result === null,
  }
}

/** Every tool the user has, oldest first, each with its latest result. */
export async function fetchInventoryTools(client: SupabaseClient): Promise<InventoryTool[]> {
  const tools = await client
    .from('inventory_tools')
    .select(TOOL_COLUMNS)
    .order('created_at', { ascending: true })
    .order('id', { ascending: true })
  if (tools.error) throw tools.error
  return z.array(ToolRowSchema).parse(tools.data).map(toTool)
}

/** One tool by its id, or null when the user has no such tool (or the id isn't one). */
export async function fetchInventoryTool(
  client: SupabaseClient,
  toolId: string,
): Promise<InventoryTool | null> {
  // An id that isn't a uuid can't be a tool's; asking would only get a 400 back.
  if (!z.uuid().safeParse(toolId).success) return null
  const tool = await client.from('inventory_tools').select(TOOL_COLUMNS).eq('id', toolId)
  if (tool.error) throw tool.error
  const [row] = z.array(ToolRowSchema).parse(tool.data)
  return row ? toTool(row) : null
}

const IdRowSchema = z.object({ id: z.uuid() })

async function insertReturningId(
  client: SupabaseClient,
  table: 'inventories' | 'systems',
  values: Record<string, unknown>,
): Promise<string> {
  const inserted = await client.from(table).insert(values).select('id').single()
  if (inserted.error) throw inserted.error
  return IdRowSchema.parse(inserted.data).id
}

export type NewRun = {
  /** The inventory the tool goes into; null when the user has none yet. */
  inventoryId: string | null
  /** The name a new inventory gets. */
  inventoryName: string
  /** The tool's name as stored (1 to 200 characters). */
  name: string
  description: string
  result: ClassificationResult
}

/**
 * Adds a classified tool: the inventory if the user has none, the system, then its first run with
 * the inputs it used (P19's `inputs`). The database numbers the run and stamps the times. If the
 * run can't be written, the system goes again, so no tool is left without its result.
 * Returns the new tool's id.
 */
export async function saveClassifiedTool(client: SupabaseClient, run: NewRun): Promise<string> {
  const inventoryId =
    run.inventoryId ?? (await insertReturningId(client, 'inventories', { name: run.inventoryName }))
  const toolId = await insertReturningId(client, 'systems', {
    inventory_id: inventoryId,
    name: run.name,
    description: run.description,
  })
  const classification = await client.from('classifications').insert({
    system_id: toolId,
    risk_class: run.result.risk_class,
    status: run.result.status,
    law_version: run.result.law_version,
    result: run.result,
    inputs: { description: run.description, answers: {} },
  })
  if (classification.error) {
    // Best effort: the run's own error is the one to report.
    await client.from('systems').delete().eq('id', toolId)
    throw classification.error
  }
  return toolId
}
