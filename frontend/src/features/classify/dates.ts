import type { HighRiskRoute } from '@/api'
import { LANGUAGE_LOCALES, type Language } from '@/i18n'

/** The Chapter III date on each high-risk route under the original text (Art. 113). The engine
 *  dates every result by the amended text (a duty's `applies_from`, a question's `duties_from`);
 *  the original text is only a view of those dates, swapped in here (decision 026 item 11). */
export const ORIGINAL_ROUTE_DATES: Record<HighRiskRoute, string> = {
  annex_iii: '2026-08-02',
  annex_i: '2027-08-02',
}

/** A route's Chapter III date under each text: the amended one as the engine dated it, the
 *  original one from Art. 113. The one helper every screen uses for the law switch's dates (the
 *  result, the inventory, the deciding question; decision 026 item 11). Without a route the date
 *  is the same under both. */
export function routeDates(
  route: HighRiskRoute | null,
  amended: string,
): { amended: string; original: string } {
  return { amended, original: route ? ORIGINAL_ROUTE_DATES[route] : amended }
}

/** The date Art. 111(2) gives legacy high-risk systems meant for public authorities. */
export const PUBLIC_AUTHORITY_DEADLINE = '2030-08-02'

const DAY_MS = 86_400_000
const DAYS_PER_MONTH = 30.44

/** An ISO date (YYYY-MM-DD) as a calendar date, independent of the viewer's time zone. */
function parseIsoDate(isoDate: string): Date {
  return new Date(`${isoDate.slice(0, 10)}T00:00:00Z`)
}

/** "2 December 2027" / "2. Dezember 2027" (localisation.md › German dates). */
export function longDate(isoDate: string, language: Language): string {
  return new Intl.DateTimeFormat(LANGUAGE_LOCALES[language], {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(parseIsoDate(isoDate))
}

/** "2 Dec 2027" / "2. Dez. 2027", for table cells (the Inventory's "Applies from"). */
export function shortDate(isoDate: string, language: Language): string {
  return new Intl.DateTimeFormat(LANGUAGE_LOCALES[language], {
    day: 'numeric',
    month: 'short',
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
