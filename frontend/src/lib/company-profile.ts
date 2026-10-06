import type { PostgrestError, SupabaseClient } from '@supabase/supabase-js'
import { z } from 'zod'

// The company profile lives on the user's inventory (migration *_user_data_screens.sql, story P19;
// decision 026 items 7 and 22). Every field is optional ("Skip for now"), and the profile is never
// an input to classification.

export const STAFF_BANDS = ['1-9', '10-49', '50-249', '250-749', '750+'] as const
export type StaffBand = (typeof STAFF_BANDS)[number]

export const TURNOVER_BANDS = ['up_to_10m', 'up_to_50m', 'up_to_150m', 'over_150m'] as const
export type TurnoverBand = (typeof TURNOVER_BANDS)[number]

export const USED_IN = ['eu', 'eu_and_outside'] as const
export type UsedIn = (typeof USED_IN)[number]

/** sme, smc (small mid-cap) or none; the database derives it (inventories.size_class). */
export const SIZE_CLASSES = ['sme', 'smc', 'none'] as const
export type SizeClass = (typeof SIZE_CLASSES)[number]

export type CompanyProfile = {
  companyName: string | null
  staffBand: StaffBand | null
  turnoverBand: TurnoverBand | null
  /** ISO 3166-1 alpha-2 code of the country the company is established in. */
  establishedIn: string | null
  usedIn: UsedIn | null
  /** Read from the database, never written. */
  sizeClass: SizeClass | null
}

/** What the profile form writes: the profile without its derived size class. */
export type CompanyProfileInput = Omit<CompanyProfile, 'sizeClass'>

/** What the app start and the Welcome screen need to know about the user's saved data. */
export type UserDataOverview = {
  /** The inventory the profile is written to; null until the user has one. */
  inventoryId: string | null
  /** The saved profile, or null while none of its fields is set. */
  profile: CompanyProfile | null
  /** The tools across all the user's inventories. */
  toolCount: number
}

export const EMPTY_OVERVIEW: UserDataOverview = { inventoryId: null, profile: null, toolCount: 0 }

const SME_STAFF_BANDS: readonly StaffBand[] = ['1-9', '10-49', '50-249']
const SME_TURNOVER_BANDS: readonly TurnoverBand[] = ['up_to_10m', 'up_to_50m']

/**
 * The size class the database derives from the two bands (inventories.size_class, P19), for the
 * form to show before saving. SME: under 250 staff and turnover up to EUR 50 m; small mid-cap:
 * otherwise under 750 staff and up to EUR 150 m. Turnover only: the balance-sheet alternatives
 * aren't applied. Keep in step with the migration.
 */
export function deriveSizeClass(
  staffBand: StaffBand | null,
  turnoverBand: TurnoverBand | null,
): SizeClass | null {
  if (staffBand === null || turnoverBand === null) return null
  if (SME_STAFF_BANDS.includes(staffBand) && SME_TURNOVER_BANDS.includes(turnoverBand)) return 'sme'
  if (staffBand !== '750+' && turnoverBand !== 'over_150m') return 'smc'
  return 'none'
}

/** True when the staff band alone would allow an SME (under 250 staff). */
export function hasSmeStaffBand(staffBand: StaffBand | null): boolean {
  return staffBand !== null && SME_STAFF_BANDS.includes(staffBand)
}

const PROFILE_COLUMNS =
  'id, company_name, staff_band, turnover_band, established_in, used_in, size_class'

const InventoryRowSchema = z.object({
  id: z.string().min(1),
  company_name: z.string().nullable(),
  staff_band: z.enum(STAFF_BANDS).nullable(),
  turnover_band: z.enum(TURNOVER_BANDS).nullable(),
  established_in: z.string().nullable(),
  used_in: z.enum(USED_IN).nullable(),
  size_class: z.enum(SIZE_CLASSES).nullable(),
})
type InventoryRow = z.infer<typeof InventoryRowSchema>

function toProfile(row: InventoryRow): CompanyProfile | null {
  const profile: CompanyProfile = {
    companyName: row.company_name,
    staffBand: row.staff_band,
    turnoverBand: row.turnover_band,
    establishedIn: row.established_in,
    usedIn: row.used_in,
    sizeClass: row.size_class,
  }
  const isEmpty =
    profile.companyName === null &&
    profile.staffBand === null &&
    profile.turnoverBand === null &&
    profile.establishedIn === null &&
    profile.usedIn === null
  return isEmpty ? null : profile
}

/**
 * Reads the user's profile and tool count. The profile is the oldest inventory that has one (an
 * import may add more inventories); without one, the oldest inventory is where a profile goes.
 */
export async function fetchUserDataOverview(client: SupabaseClient): Promise<UserDataOverview> {
  const inventories = await client
    .from('inventories')
    .select(PROFILE_COLUMNS)
    .order('created_at', { ascending: true })
    .order('id', { ascending: true })
  if (inventories.error) throw inventories.error
  const rows = z.array(InventoryRowSchema).parse(inventories.data)

  const systems = await client.from('systems').select('id', { count: 'exact', head: true })
  if (systems.error) throw systems.error

  const withProfile = rows.find((row) => toProfile(row) !== null)
  const target = withProfile ?? rows[0]
  return {
    inventoryId: target?.id ?? null,
    profile: withProfile ? toProfile(withProfile) : null,
    toolCount: systems.count ?? 0,
  }
}

function toColumns(input: CompanyProfileInput): Record<string, string | null> {
  return {
    company_name: input.companyName,
    staff_band: input.staffBand,
    turnover_band: input.turnoverBand,
    established_in: input.establishedIn,
    used_in: input.usedIn,
  }
}

/**
 * Writes the profile onto the user's inventory, or creates the inventory (named `inventoryName`)
 * when the user has none yet.
 */
export async function saveCompanyProfile(
  client: SupabaseClient,
  inventoryId: string | null,
  input: CompanyProfileInput,
  inventoryName: string,
): Promise<void> {
  const columns = toColumns(input)
  const written = inventoryId
    ? await client.from('inventories').update(columns).eq('id', inventoryId)
    : await client.from('inventories').insert({ name: inventoryName, ...columns })
  if (written.error) throw written.error
}

/** Rows added by an import, per kind (import_my_data's answer). */
const ImportCountsSchema = z.object({
  inventories: z.number().int().nonnegative(),
  systems: z.number().int().nonnegative(),
})
export type ImportCounts = z.infer<typeof ImportCountsSchema>

/** The largest file import_my_data accepts (its max_bytes, decision 027). */
export const IMPORT_MAX_BYTES = 4 * 1024 * 1024

/** A file that isn't a Klar export, caught before it is sent. */
export class ImportFileError extends Error {
  readonly reason: 'not-json' | 'too-large'

  constructor(reason: 'not-json' | 'too-large') {
    super(`The import file was refused: ${reason}.`)
    this.name = 'ImportFileError'
    this.reason = reason
  }
}

/** Restores a file exported from Your data (export_my_data) through import_my_data. */
export async function importUserData(client: SupabaseClient, file: File): Promise<ImportCounts> {
  if (file.size > IMPORT_MAX_BYTES) throw new ImportFileError('too-large')
  let data: unknown
  try {
    data = JSON.parse(await file.text())
  } catch {
    throw new ImportFileError('not-json')
  }
  const imported = await client.rpc('import_my_data', { data })
  if (imported.error) throw imported.error
  return ImportCountsSchema.parse(imported.data)
}

/** How a failed write is shown: each kind has its own message. */
export type WriteFailure = 'storage-full' | 'too-large' | 'bad-file' | 'failed'

function isPostgrestError(error: unknown): error is PostgrestError {
  return typeof error === 'object' && error !== null && 'code' in error && 'message' in error
}

/**
 * Sorts a failed write. PT507 is the storage budget (decision 027) and PT413 the import cap; 22023
 * is a file that isn't an export. Other errors stay generic: their text may carry server details.
 */
export function classifyWriteFailure(error: unknown): WriteFailure {
  if (error instanceof ImportFileError)
    return error.reason === 'too-large' ? 'too-large' : 'bad-file'
  if (!isPostgrestError(error)) return 'failed'
  switch (error.code) {
    case 'PT507':
      return 'storage-full'
    case 'PT413':
      return 'too-large'
    case '22023':
    case '22P02':
    case '22007':
    case '23502':
    case '23514':
      return 'bad-file'
    default:
      return 'failed'
  }
}
