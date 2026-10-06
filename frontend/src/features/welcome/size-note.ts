import type { LawVersion } from '@/components/LawSwitch'
import {
  deriveSizeClass,
  hasSmeStaffBand,
  type StaffBand,
  type TurnoverBand,
} from '@/lib/company-profile'

import type { QuotedProvision } from './LawQuote'

/** The line shown: noneOriginal is "not an SME" under the original 2024 text. */
export type SizeLine = 'sme' | 'smc' | 'none' | 'noneOriginal'

/** A balance-sheet test Klar can't apply that might still change the class. */
export type SizeCaveat = 'maybeSme' | 'maybeSmc'

export type SizeNote = { line: SizeLine; caveats: SizeCaveat[]; quotes: QuotedProvision[] }

/**
 * What the derived line says under a law version. Small mid-caps exist only in the amended text
 * (Art. 3(14b), Art. 99(6a)); under the original, a small mid-cap by bands is shown as not an SME.
 * The bands use turnover only, so a caveat names the balance-sheet route where it could change the
 * class: under 250 staff an SME (up to EUR 43 m); and, under the amended text, a company shown as
 * neither with under 750 staff a small mid-cap (up to EUR 129 m, whatever its turnover,
 * Recommendation (EU) 2025/1099). Under 250 staff, "neither" gets both caveats.
 */
export function describeSize(
  staffBand: StaffBand | null,
  turnoverBand: TurnoverBand | null,
  law: LawVersion,
): SizeNote | null {
  const sizeClass = deriveSizeClass(staffBand, turnoverBand)
  if (sizeClass === null) return null
  const isAmended = law === 'amended'
  if (sizeClass === 'sme') return { line: 'sme', caveats: [], quotes: ['art99_3', 'art99_6'] }

  const caveats: SizeCaveat[] = hasSmeStaffBand(staffBand) ? ['maybeSme'] : []
  if (!isAmended) return { line: 'noneOriginal', caveats, quotes: ['art99_3', 'art99_6'] }
  if (sizeClass === 'smc') return { line: 'smc', caveats, quotes: ['art99_3', 'art99_6a'] }
  const noneCaveats: SizeCaveat[] = staffBand === '750+' ? caveats : [...caveats, 'maybeSmc']
  return { line: 'none', caveats: noneCaveats, quotes: ['art99_3', 'art99_6', 'art99_6a'] }
}
