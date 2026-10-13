import type { Obligation } from '@/api'
import type { LawVersion } from '@/components/LawSwitch'
import type { Language } from '@/i18n'
import type { SizeClass } from '@/lib/company-profile'

/** The company profile's size classes the relief notes are for (P31, user 2026-10-13). */
const RELIEVED_SIZES: ReadonlySet<SizeClass> = new Set(['sme', 'smc'])

/** The relief the obligations table gives an SME or a small mid-cap for `duty`, in `language`
 *  (the English note when the German one is missing, so it is never dropped); null for another
 *  company, without a profile, and under the original text, as the notes name small mid-caps,
 *  which only the Omnibus added. The reports read it the same way (backend `is_relieved`). */
export function reliefNote(
  duty: Obligation,
  language: Language,
  sizeClass: SizeClass | null | undefined,
  shown: LawVersion,
): string | null {
  if (!sizeClass || !RELIEVED_SIZES.has(sizeClass) || shown !== 'amended') return null
  return (language === 'de' ? duty.relief_note_de : null) ?? duty.relief_note ?? null
}
