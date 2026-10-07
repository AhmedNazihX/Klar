// An in-memory stand-in for the user's rows behind P3's and P19's functions, as MSW handlers:
// my_data_counts, export_my_data, import_my_data and delete_my_data, plus the sign-out. It keeps
// the export format (aiact-user-data, version 1), so a test can download a file, delete
// everything, import the file and compare (Your data, P12).
import { http, HttpResponse, type HttpHandler } from 'msw'

import { anonymousSession, SIGNUP_URL, SUPABASE_URL } from './supabase-fixtures'
import { IMPORT_URL, inventoryRow, userDataHandlers } from './user-data-handlers'

export const COUNTS_URL = `${SUPABASE_URL}/rest/v1/rpc/my_data_counts`
export const EXPORT_URL = `${SUPABASE_URL}/rest/v1/rpc/export_my_data`
export const DELETE_URL = `${SUPABASE_URL}/rest/v1/rpc/delete_my_data`
export const LOGOUT_URL = `${SUPABASE_URL}/auth/v1/logout`

/** import_my_data's max_bytes less 1 kB (private.storage_budget(), decision 027). */
export const STORAGE_BUDGET_BYTES = 4 * 1024 * 1024 - 1024

export type StoredSystem = {
  name: string
  description: string
  created_at: string
  classifications: Record<string, unknown>[]
  interview_answers: { template: string; question_key: string; answer: string }[]
  duty_progress: { obligation_key: string; created_at: string }[]
}

export type StoredInventory = {
  name: string
  company_name: string | null
  staff_band: string | null
  turnover_band: string | null
  established_in: string | null
  used_in: string | null
  created_at: string
  systems: StoredSystem[]
}

export type UserDataStore = {
  /** The rows as they are now. */
  inventories: () => StoredInventory[]
  /** Calls per function, to show what was (and wasn't) sent. */
  calls: {
    signup: number
    counts: number
    export: number
    import: number
    delete: number
    logout: number
  }
  handlers: HttpHandler[]
}

const PROFILE_FIELDS = [
  'company_name',
  'staff_band',
  'turnover_band',
  'established_in',
  'used_in',
] as const

function hasProfile(inventory: StoredInventory): boolean {
  return PROFILE_FIELDS.some((field) => inventory[field] !== null)
}

function sum(inventories: StoredInventory[], count: (system: StoredSystem) => number): number {
  return inventories.flatMap((inventory) => inventory.systems).reduce((n, s) => n + count(s), 0)
}

/** Rows per kind, as import_my_data and delete_my_data answer. */
function rowCountsOf(inventories: StoredInventory[]): Record<string, number> {
  return {
    inventories: inventories.length,
    systems: sum(inventories, () => 1),
    classifications: sum(inventories, (s) => s.classifications.length),
    interview_answers: sum(inventories, (s) => s.interview_answers.length),
    duty_progress: sum(inventories, (s) => s.duty_progress.length),
  }
}

/** my_data_counts' answer. */
function countsOf(inventories: StoredInventory[]): Record<string, number> {
  return {
    ...rowCountsOf(inventories),
    company_profiles: inventories.filter(hasProfile).length,
    storage_bytes: JSON.stringify(inventories).length,
    storage_budget_bytes: STORAGE_BUDGET_BYTES,
  }
}

function isExport(body: unknown): body is { data: { inventories: StoredInventory[] } } {
  if (typeof body !== 'object' || body === null || !('data' in body)) return false
  const data = body.data as Record<string, unknown> | null
  return data?.format === 'aiact-user-data' && data.version === 1 && Array.isArray(data.inventories)
}

/** The store, starting from `initial` (copied, so the test keeps its own). */
export function createUserDataStore(initial: StoredInventory[]): UserDataStore {
  let inventories = structuredClone(initial)
  const calls = { signup: 0, counts: 0, export: 0, import: 0, delete: 0, logout: 0 }
  const profileRows = () =>
    inventories.map((inventory) =>
      inventoryRow(Object.fromEntries(PROFILE_FIELDS.map((field) => [field, inventory[field]]))),
    )
  const handlers: HttpHandler[] = [
    // Ahead of userDataHandlers' own sign-up, so each anonymous sign-in is counted.
    http.post(SIGNUP_URL, () => {
      calls.signup += 1
      return HttpResponse.json(anonymousSession())
    }),
    ...userDataHandlers(profileRows, () => sum(inventories, () => 1)),
    http.post(COUNTS_URL, () => {
      calls.counts += 1
      return HttpResponse.json(countsOf(inventories))
    }),
    http.post(EXPORT_URL, () => {
      calls.export += 1
      return HttpResponse.json({
        format: 'aiact-user-data',
        version: 1,
        exported_at: '2026-10-07T09:00:00+00:00',
        inventories,
      })
    }),
    http.post(IMPORT_URL, async ({ request }) => {
      calls.import += 1
      const body: unknown = await request.json()
      if (!isExport(body)) {
        return HttpResponse.json(
          { code: '22023', message: 'not an export', details: null, hint: null },
          { status: 400 },
        )
      }
      const added = structuredClone(body.data.inventories)
      inventories = [...inventories, ...added]
      return HttpResponse.json(rowCountsOf(added))
    }),
    http.post(DELETE_URL, () => {
      calls.delete += 1
      const deleted = rowCountsOf(inventories)
      inventories = []
      return HttpResponse.json(deleted)
    }),
    http.post(LOGOUT_URL, () => {
      calls.logout += 1
      return new HttpResponse(null, { status: 204 })
    }),
  ]
  return { inventories: () => inventories, calls, handlers }
}
