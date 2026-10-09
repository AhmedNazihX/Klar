// The inventory's Data API calls (P6), against MSW at the PostgREST boundary: what each call sends
// and how it reads the rows back. RLS, the view's latest-run rule and the save's single
// transaction are the database's (backend/tests/db/test_inventory_tools.py,
// test_save_classified_tool.py).
import { http, HttpResponse } from 'msw'
import { afterAll, describe, expect, it } from 'vitest'

import { storedBeforeDecision030, WORKED_EXAMPLE } from '@/test/classify-fixtures'
import {
  INVENTORY_TOOLS_URL,
  inventoryToolsHandler,
  SAVE_TOOL_URL,
  toolRow,
} from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { SUPABASE_URL } from '@/test/supabase-fixtures'
import { INVENTORY_ID } from '@/test/user-data-handlers'

import { fetchInventoryTool, fetchInventoryTools, saveClassifiedTool } from './inventory'
import { createSupabase } from './supabase'

const client = createSupabase({ url: SUPABASE_URL, anonKey: 'test-anon-key' })
if (!client) throw new Error('The test client needs a Supabase configuration.')

afterAll(async () => {
  await client.auth.stopAutoRefresh()
})

const SYSTEM_ID = '9a0c5e43-3c1e-4a5e-9d55-2f6f0b7b9c01'

describe('fetchInventoryTools', () => {
  it('reads every tool with its latest result from inventory_tools, oldest first', async () => {
    let query = new URLSearchParams()
    const rows = [
      toolRow('Applicant screening', WORKED_EXAMPLE),
      toolRow('Route planner', null),
      toolRow('Edited file', { risk_class: 'harmless' }),
      toolRow('Unnamed', WORKED_EXAMPLE, { name: null }),
    ]
    server.use(
      http.get(INVENTORY_TOOLS_URL, ({ request }) => {
        query = new URL(request.url).searchParams
        return HttpResponse.json(rows)
      }),
    )
    const tools = await fetchInventoryTools(client)

    expect(query.get('select')).toBe('id,name,description,created_at,run_no,result')
    expect(query.get('order')).toBe('created_at.asc,id.asc')
    expect(
      tools.map((tool) => [tool.name, tool.result?.risk_class, tool.hasUnreadableResult]),
    ).toEqual([
      ['Applicant screening', 'high_risk', false],
      ['Route planner', undefined, false],
      ['Edited file', undefined, true],
      // A tool the user gave no name keeps none: screens name it in their own language.
      [null, 'high_risk', false],
    ])
    expect(tools[0]?.toolId).toBe(rows[0]?.['id'])
    expect(tools[0]?.description).toBe(rows[0]?.['description'])
  })

  it('reads a result whose class rests on a check not assessed as no result, not unreadable', async () => {
    server.use(inventoryToolsHandler(() => [toolRow('Before 030', storedBeforeDecision030())]))
    const [tool] = await fetchInventoryTools(client)
    expect(tool?.result).toBeNull()
    expect(tool?.hasUnreadableResult).toBe(false)
  })

  it('passes a read error on', async () => {
    server.use(
      http.get(INVENTORY_TOOLS_URL, () =>
        HttpResponse.json({ code: '42501', message: 'permission denied' }, { status: 401 }),
      ),
    )
    await expect(fetchInventoryTools(client)).rejects.toMatchObject({ code: '42501' })
  })
})

describe('fetchInventoryTool', () => {
  it('reads one tool by its id', async () => {
    const rows = [toolRow('Applicant screening', WORKED_EXAMPLE), toolRow('Other', WORKED_EXAMPLE)]
    server.use(inventoryToolsHandler(() => rows))
    const id = String(rows[1]?.['id'])
    const tool = await fetchInventoryTool(client, id)
    expect(tool?.name).toBe('Other')
    expect(tool?.toolId).toBe(id)
  })

  it('is null for an id the user has no tool for', async () => {
    server.use(inventoryToolsHandler(() => []))
    expect(await fetchInventoryTool(client, SYSTEM_ID)).toBeNull()
  })

  it('never asks for an id that is not a uuid', async () => {
    let requests = 0
    server.use(
      http.get(INVENTORY_TOOLS_URL, () => {
        requests += 1
        return HttpResponse.json([])
      }),
    )
    expect(await fetchInventoryTool(client, 'applicant-screening')).toBeNull()
    expect(requests).toBe(0)
  })
})

/** Records each save_classified_tool call's arguments; it answers with the new tool's id, or
 *  with `error` when given. Any other write would go unanswered (MSW errors on it). */
function recordSaves(error: { status: number; code: string } | null = null) {
  const calls: unknown[] = []
  server.use(
    http.post(SAVE_TOOL_URL, async ({ request }) => {
      calls.push(await request.json())
      return error
        ? HttpResponse.json({ code: error.code, message: 'refused' }, { status: error.status })
        : HttpResponse.json(SYSTEM_ID)
    }),
  )
  return calls
}

const NEW_RUN = {
  toolId: null,
  inventoryName: 'AI inventory',
  name: 'Applicant screening',
  description: 'Ranks job applicants.',
  result: WORKED_EXAMPLE,
}

describe('saveClassifiedTool', () => {
  it('saves the tool and its first run in one call into the inventory', async () => {
    const calls = recordSaves()
    const id = await saveClassifiedTool(client, { ...NEW_RUN, inventoryId: INVENTORY_ID })

    expect(id).toBe(SYSTEM_ID)
    expect(calls).toEqual([
      {
        target_inventory_id: INVENTORY_ID,
        new_inventory_name: 'AI inventory',
        tool_name: 'Applicant screening',
        tool_description: 'Ranks job applicants.',
        tool_result: WORKED_EXAMPLE,
        target_system_id: null,
      },
    ])
  })

  it("saves a run on the user's tool as its next run, in the same call", async () => {
    const calls = recordSaves()
    const id = await saveClassifiedTool(client, {
      ...NEW_RUN,
      toolId: SYSTEM_ID,
      inventoryId: INVENTORY_ID,
    })

    expect(id).toBe(SYSTEM_ID)
    expect(calls).toEqual([
      expect.objectContaining({ target_system_id: SYSTEM_ID, tool_name: 'Applicant screening' }),
    ])
  })

  it('leaves the inventory to the database when the user has none, and an unnamed tool unnamed', async () => {
    const calls = recordSaves()
    await saveClassifiedTool(client, { ...NEW_RUN, inventoryId: null, name: null })
    expect(calls).toEqual([
      expect.objectContaining({
        target_inventory_id: null,
        new_inventory_name: 'AI inventory',
        tool_name: null,
      }),
    ])
  })

  it('reports the database error when the save is refused', async () => {
    const calls = recordSaves({ status: 507, code: 'PT507' })
    await expect(
      saveClassifiedTool(client, { ...NEW_RUN, inventoryId: INVENTORY_ID }),
    ).rejects.toMatchObject({ code: 'PT507' })
    // One call: nothing to take back, the database saved all of it or none.
    expect(calls).toHaveLength(1)
  })
})
