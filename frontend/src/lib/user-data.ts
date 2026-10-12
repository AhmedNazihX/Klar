import type { SupabaseClient } from '@supabase/supabase-js'
import { z } from 'zod'

import { LANGUAGE_LOCALES, type Language } from '@/i18n'

// Your data (story P12) over P3's and P19's functions: my_data_counts, export_my_data and
// delete_my_data. Each one runs as the signed-in user, so row-level security keeps it to their rows.

const count = z.number().int().nonnegative()

const MyDataCountsSchema = z.object({
  inventories: count,
  company_profiles: count,
  systems: count,
  classifications: count,
  interview_answers: count,
  duty_progress: count,
  storage_bytes: count,
  storage_budget_bytes: count,
})

/** What Klar keeps for the user, per kind, and the bytes it takes against the budget. */
export type MyDataCounts = {
  companyProfiles: number
  systems: number
  classifications: number
  interviewAnswers: number
  dutyProgress: number
  storageBytes: number
  storageBudgetBytes: number
}

/** Reads the user's counts (my_data_counts). There is no question count: Q&A isn't stored. */
export async function fetchMyDataCounts(client: SupabaseClient): Promise<MyDataCounts> {
  const answer = await client.rpc('my_data_counts')
  if (answer.error) throw answer.error
  const counts = MyDataCountsSchema.parse(answer.data)
  return {
    companyProfiles: counts.company_profiles,
    systems: counts.systems,
    classifications: counts.classifications,
    interviewAnswers: counts.interview_answers,
    dutyProgress: counts.duty_progress,
    storageBytes: counts.storage_bytes,
    storageBudgetBytes: counts.storage_budget_bytes,
  }
}

const BYTES_PER_KB = 1024
const BYTES_PER_MB = 1024 * 1024

/** "12 kB", "1.5 MB": a storage figure in the reader's locale. Under a kilobyte reads "< 1 kB",
 *  so a stored row never shows as "0 kB"; nothing at all does. */
export function formatBytes(bytes: number, language: Language): string {
  const isMegabytes = bytes >= BYTES_PER_MB
  const format = new Intl.NumberFormat(LANGUAGE_LOCALES[language], {
    style: 'unit',
    unit: isMegabytes ? 'megabyte' : 'kilobyte',
    maximumFractionDigits: isMegabytes ? 1 : 0,
  })
  if (bytes > 0 && bytes < BYTES_PER_KB) return `< ${format.format(1)}`
  return format.format(bytes / (isMegabytes ? BYTES_PER_MB : BYTES_PER_KB))
}

// The envelope export_my_data writes and import_my_data checks; the rest goes through unread.
const UserDataExportSchema = z.looseObject({
  format: z.literal('aiact-user-data'),
  version: z.literal(1),
  inventories: z.array(z.unknown()),
})
export type UserDataExport = z.infer<typeof UserDataExportSchema>

/** The user's data as one document (export_my_data), ready to save as a file. */
export async function exportUserData(client: SupabaseClient): Promise<UserDataExport> {
  const answer = await client.rpc('export_my_data')
  if (answer.error) throw answer.error
  return UserDataExportSchema.parse(answer.data)
}

/** The file's name, dated in the user's own time zone: klar-data-2026-10-07.json. */
export function exportFileName(date: Date): string {
  const day = [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
  return `klar-data-${day}.json`
}

// The browser starts the download on click; the address is released once that has happened.
const REVOKE_AFTER_MS = 1000

/** Saves `document` as a JSON file through the browser's download, without any request. */
export function downloadJson(document: unknown, fileName: string): void {
  const blob = new Blob([JSON.stringify(document, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = window.document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), REVOKE_AFTER_MS)
}

/**
 * Deletes everything the user has stored (delete_my_data), then ends the session in this browser.
 * The anonymous account left behind holds no data and is purged after 30 days (decision 013).
 */
export async function deleteUserData(client: SupabaseClient): Promise<void> {
  const deleted = await client.rpc('delete_my_data')
  if (deleted.error) throw deleted.error
  // supabase-js drops the stored session even when the server's sign-out fails, so a failure here
  // never leaves this browser signed in; the data is gone either way, so it isn't reported.
  await client.auth.signOut()
}
