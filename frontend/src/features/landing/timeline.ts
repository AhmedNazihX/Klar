// The AI Act's application dates on the landing page, as amended by the Digital Omnibus (Art. 113;
// Art. 111(4) for the marking grace period). The sentence for each date is in the locale files under
// landing.dates.items.<id>.

export type TimelineDateId = 'transparency' | 'prohibitions' | 'annexIII' | 'annexI'

export const TIMELINE_DATES: readonly { id: TimelineDateId; isoDate: string }[] = [
  // Art. 113, second paragraph: the Regulation, Art. 50 included, applies from 2 August 2026.
  { id: 'transparency', isoDate: '2026-08-02' },
  // Art. 113(a): Art. 5(1)(ba) and (bb); Art. 111(4): Art. 50(2) for systems placed before 2 Aug 2026.
  { id: 'prohibitions', isoDate: '2026-12-02' },
  // Art. 113(c)(i): high-risk under Art. 6(2) and Annex III.
  { id: 'annexIII', isoDate: '2027-12-02' },
  // Art. 113(c)(ii): high-risk under Art. 6(1) and Annex I.
  { id: 'annexI', isoDate: '2028-08-02' },
]

/** The start of a calendar day in UTC, in ms, so a date compares the same in every time zone. */
function dayOf(date: Date): number {
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
}

function dayOfIso(isoDate: string): number {
  return Date.parse(`${isoDate}T00:00:00Z`)
}

/** True when `isoDate` is today or earlier: the date applies already. */
export function hasPassed(isoDate: string, today: Date): boolean {
  return dayOfIso(isoDate) <= dayOf(today)
}

/**
 * Where today falls on the line, counted in dates: 0 on the first date, 1 on the second, 0.5
 * halfway between them. Clamped to the line, so a day before the first date is 0 and a day after
 * the last is the last index.
 */
export function todayPosition(isoDates: readonly string[], today: Date): number {
  const now = dayOf(today)
  const days = isoDates.map(dayOfIso)
  const last = days.length - 1
  if (last < 0) return 0
  const next = days.findIndex((day) => day > now)
  if (next === -1) return last
  if (next === 0) return 0
  const from = days[next - 1] ?? now
  const to = days[next] ?? now
  return next - 1 + (now - from) / (to - from)
}

/** How many dates have passed by `today`: where Today goes in the dates' reading order. */
export function passedCount(isoDates: readonly string[], today: Date): number {
  return isoDates.filter((isoDate) => hasPassed(isoDate, today)).length
}
