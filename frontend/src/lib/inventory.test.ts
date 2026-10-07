// The inventory's Data API calls (P6), against MSW at the PostgREST boundary: what each call sends
// and how it reads the rows back. RLS and the view's latest-run rule are the database's
// (backend/tests/db/test_inventory_tools.py).
import { http, HttpResponse } from 'msw'
import { afterAll, describe, expect, it } from 'vitest'

import { WORKED_EXAMPLE } from '@/test/classify-fixtures'
import {
  CLASSIFICATIONS_URL,
  INVENTORY_TOOLS_URL,
  inventoryToolsHandler,
  toolRow,
} from '@/test/inventory-fixtures'
import { server } from '@/test/msw-server'
import { SUPABASE_URL } from '@/test/supabase-fixtures'
import { INVENTORIES_URL, INVENTORY_ID, SYSTEMS_URL } from '@/test/user-data-handlers'

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
    ])
    expect(tools[0]?.toolId).toBe(rows[0]?.['id'])
    expect(tools[0]?.description).toBe(rows[0]?.['description'])
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

/** Records the inserts the save makes, answering each with a new row's id. */
function recordWrites(classificationStatus = 201) {
  const writes: { table: string; body: unknown }[] = []
  const deleted: string[] = []
  server.use(
    http.post(INVENTORIES_URL, async ({ request }) => {
      writes.push({ table: 'inventories', body: await request.json() })
      return HttpResponse.json({ id: INVENTORY_ID }, { status: 201 })
    }),
    http.post(SYSTEMS_URL, async ({ request }) => {
      writes.push({ table: 'systems', body: await request.json() })
      return HttpResponse.json({ id: SYSTEM_ID }, { status: 201 })
    }),
    http.post(CLASSIFICATIONS_URL, async ({ request }) => {
      writes.push({ table: 'classifications', body: await request.json() })
      return classificationStatus === 201
        ? new HttpResponse(null, { status: 201 })
        : HttpResponse.json({ code: 'PT507', message: 'storage full' }, { status: 400 })
    }),
    http.delete(SYSTEMS_URL, ({ request }) => {
      deleted.push(new URL(request.url).searchParams.get('id') ?? '')
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return { writes, deleted }
}

const NEW_RUN = {
  inventoryName: 'AI inventory',
  name: 'Applicant screening',
  description: 'Ranks job applicants.',
  result: WORKED_EXAMPLE,
}

describe('saveClassifiedTool', () => {
  it('adds the system and its first run, with the inputs it used, to the inventory', async () => {
    const { writes } = recordWrites()
    const id = await saveClassifiedTool(client, { ...NEW_RUN, inventoryId: INVENTORY_ID })

    expect(id).toBe(SYSTEM_ID)
    expect(writes).toEqual([
      {
        table: 'systems',
        body: {
          inventory_id: INVENTORY_ID,
          name: 'Applicant screening',
          description: 'Ranks job applicants.',
        },
      },
      {
        table: 'classifications',
        body: {
          system_id: SYSTEM_ID,
          risk_class: 'high_risk',
          status: 'needs_more_information',
          law_version: 'amended',
          result: WORKED_EXAMPLE,
          inputs: { description: 'Ranks job applicants.', answers: {} },
        },
      },
    ])
  })

  it('creates the inventory first when the user has none', async () => {
    const { writes } = recordWrites()
    await saveClassifiedTool(client, { ...NEW_RUN, inventoryId: null })
    expect(writes.map((write) => write.table)).toEqual([
      'inventories',
      'systems',
      'classifications',
    ])
    expect(writes[0]?.body).toEqual({ name: 'AI inventory' })
    expect(writes[1]?.body).toMatchObject({ inventory_id: INVENTORY_ID })
  })

  it('takes the system back out when its run cannot be written, and reports the run error', async () => {
    const { deleted } = recordWrites(400)
    await expect(
      saveClassifiedTool(client, { ...NEW_RUN, inventoryId: INVENTORY_ID }),
    ).rejects.toMatchObject({ code: 'PT507' })
    expect(deleted).toEqual([`eq.${SYSTEM_ID}`])
  })
})
