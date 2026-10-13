import type { LawVersion } from '@/components/LawSwitch'
import type { ReliefNotes } from '@/hooks/use-relief-notes'
import type { Language } from '@/i18n'
import type { SizeClass } from '@/lib/company-profile'

/** The company profile's size classes the relief notes are for (P31, user 2026-10-13). */
const RELIEVED_SIZES: ReadonlySet<SizeClass> = new Set(['sme', 'smc'])

/** Whether the duties show their relief notes: for an SME or a small mid-cap, under the amended
 *  text only, as the notes name small mid-caps, which only the Omnibus added; not without a
 *  profile. The reports decide the same way (backend `is_relieved`). */
export function isRelieved(sizeClass: SizeClass | null | undefined, shown: LawVersion): boolean {
  return sizeClass != null && RELIEVED_SIZES.has(sizeClass) && shown === 'amended'
}

/** A duty's relief note in `language`, from the obligations table's `notes` for its key
 *  (`useReliefNotes`), as the reports take it; null when the table gives it none, and never the
 *  other language's note in its place. */
export function reliefNote(notes: ReliefNotes | undefined, language: Language): string | null {
  if (!notes) return null
  return (language === 'de' ? notes.relief_note_de : notes.relief_note) ?? null
}
