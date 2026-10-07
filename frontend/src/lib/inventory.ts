import type { SupabaseClient } from '@supabase/supabase-js'
import { z } from 'zod'

import type { ClassificationResult } from '@/api'

import { parseStoredResult } from './stored-result'

// The user's tools and their runs in Supabase (story P6): systems and classifications (P3, P19),
// read through the inventory_tools view (each tool with its latest run, owner-only RLS) and
// written through save_classified_tool (one transaction).

/** One tool in the inventory, with its latest result. */
export type InventoryTool = {
  toolId: string
  /** Null when the user gave none: screens then show "Your tool" in their language. */
  name: string | null
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
  name: z.string().nullable(),
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

export type NewRun = {
  /** The inventory the tool goes into; null when the user has none yet. */
  inventoryId: string | null
  /** The name a new inventory gets. */
  inventoryName: string
  /** The tool's name (1 to 200 characters), or null when the user gave none. */
  name: string | null
  description: string
  result: ClassificationResult
}

/**
 * Adds a classified tool through save_classified_tool: the inventory if the user has none, the
 * system, then its first run with the inputs it used (P19's `inputs`), all in one transaction,
 * so a run that can't be written leaves no tool behind. The database numbers the run and stamps
 * the times. Returns the new tool's id.
 */
export async function saveClassifiedTool(client: SupabaseClient, run: NewRun): Promise<string> {
  const saved = await client.rpc('save_classified_tool', {
    target_inventory_id: run.inventoryId,
    new_inventory_name: run.inventoryName,
    tool_name: run.name,
    tool_description: run.description,
    tool_result: run.result,
  })
  if (saved.error) throw saved.error
  return z.uuid().parse(saved.data)
}
