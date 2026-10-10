// MSW handlers for the user's data in Supabase (PostgREST): the inventories with their company
// profile, the tool count and import_my_data. Each test passes the rows it needs.
import { http, HttpResponse, type HttpHandler } from 'msw'

import { inventoryToolsHandler } from './inventory-fixtures'
import { anonymousSession, SIGNUP_URL, SUPABASE_URL } from './supabase-fixtures'

export const INVENTORIES_URL = `${SUPABASE_URL}/rest/v1/inventories`
export const SYSTEMS_URL = `${SUPABASE_URL}/rest/v1/systems`
export const IMPORT_URL = `${SUPABASE_URL}/rest/v1/rpc/import_my_data`
export const INVENTORY_ID = '0d6c1c55-1d2e-4f00-9a3b-6b3c3f1a2b10'

/** An inventories row as PostgREST returns it; every profile field null unless given. */
export function inventoryRow(fields: Record<string, string | null> = {}): Record<string, unknown> {
  return {
    id: INVENTORY_ID,
    company_name: null,
    staff_band: null,
    turnover_band: null,
    established_in: null,
    used_in: null,
    size_class: null,
    ...fields,
  }
}

/** The signup a fresh client makes, then the reads: these inventories, this many tools and, for
 *  the Inventory screen (P6), these inventory_tools rows (none unless given). */
export function userDataHandlers(
  rows: () => Record<string, unknown>[],
  toolCount: () => number,
  tools: () => Record<string, unknown>[] = () => [],
): HttpHandler[] {
  return [
    http.post(SIGNUP_URL, () => HttpResponse.json(anonymousSession())),
    http.get(INVENTORIES_URL, () => HttpResponse.json(rows())),
    inventoryToolsHandler(tools),
    http.head(
      SYSTEMS_URL,
      () =>
        new HttpResponse(null, {
          status: 200,
          headers: { 'Content-Range': `*/${String(toolCount())}` },
        }),
    ),
  ]
}
