import type { HighRiskRoute } from '@/api'
import type { Language } from '@/i18n'

/** The Chapter III date on each high-risk route, under the amended and the original text
 *  (Art. 113; decision 026 item 11 swaps only these route dates under the original text). */
export const ROUTE_DATES: Record<HighRiskRoute, { amended: string; original: string }> = {
  annex_iii: { amended: '2027-12-02', original: '2026-08-02' },
  annex_i: { amended: '2028-08-02', original: '2027-08-02' },
}

/** The date Art. 111(2) gives legacy high-risk systems meant for public authorities. */
export const PUBLIC_AUTHORITY_DEADLINE = '2030-08-02'

const LOCALES: Record<Language, string> = { en: 'en-GB', de: 'de-DE' }
const DAY_MS = 86_400_000
const DAYS_PER_MONTH = 30.44

/** An ISO date (YYYY-MM-DD) as a calendar date, independent of the viewer's time zone. */
function parseIsoDate(isoDate: string): Date {
  return new Date(`${isoDate.slice(0, 10)}T00:00:00Z`)
}

/** "2 December 2027" / "2. Dezember 2027" (localisation.md › German dates). */
export function longDate(isoDate: string, language: Language): string {
  return new Intl.DateTimeFormat(LOCALES[language], {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(parseIsoDate(isoDate))
}

/** Whole months from `today` to the date, rounded; 0 or less when it has already come. */
export function monthsUntil(isoDate: string, today: Date): number {
  const todayUtc = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  const days = (parseIsoDate(isoDate).getTime() - todayUtc) / DAY_MS
  if (days <= 0) return 0
  return Math.max(1, Math.round(days / DAYS_PER_MONTH))
}

/** The route of a high-risk Annex point (`annex:III:…` or `annex:I:…`), if it is one. */
export function routeOfPoint(point: string | null | undefined): HighRiskRoute | null {
  if (!point) return null
  if (point.startsWith('annex:III:')) return 'annex_iii'
  if (point.startsWith('annex:I:')) return 'annex_i'
  return null
}
