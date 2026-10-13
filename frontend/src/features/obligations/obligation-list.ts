import type { HighRiskRoute, Obligation } from '@/api'
import type { LawVersion } from '@/components/LawSwitch'
import { ORIGINAL_ROUTE_DATES, routeDates } from '@/features/classify/dates'
import { isChecked, isoDay, sortTools, type CheckedTool } from '@/features/inventory/tool-facts'
import type { InventoryTool } from '@/lib/inventory'
import { tickKey, type DutyTick } from '@/lib/duty-progress'

// The Obligations screen's list (artboard `Obligations`): every duty across the inventory, from
// each tool's latest stored result, grouped by the date it applies from or by tool, with the
// user's ticks. The dates are the results' own (amended text); under the original text only the
// route dates swap (decision 026 item 11), which the screen shows through LawDate.

/** A tool on the screen with the duties it lists there. */
export type ToolDuties = { tool: CheckedTool; duties: Obligation[] }

/** What a dated section's duties are, for the line beside its heading (artboard `Obligations`:
 *  "Transparency, Art. 50"): Art. 50's transparency duties, or one article all its duties come
 *  from; else, when a route section has the same date, "other duties", so the two read apart. */
export type SectionCategory =
  { kind: 'transparency' } | { kind: 'article'; article: string } | { kind: 'other' }

/** A section of duties dated outside a high-risk route. `hasRouteTwin` when a route section has
 *  the same (amended) date: the heading then names what the section holds, so the two read apart
 *  (P24's two "From 2 December 2027" sections). */
type DatedSection = {
  date: string
  category: SectionCategory | null
  hasRouteTwin: boolean
  tools: ToolDuties[]
}

/** The By date sections, in the screen's order. */
export type DateSection =
  /** A prohibited tool's duties: stop now (Art. 5). */
  | { kind: 'stop'; tools: ToolDuties[] }
  /** Duties whose date has come. */
  | ({ kind: 'since' } & DatedSection)
  /** Duties whose date is still ahead (an Art. 111(2) 2030 date included). */
  | ({ kind: 'from' } & DatedSection)
  /** A high-risk route's duties: its Chapter III date, which the Digital Omnibus moved. */
  | { kind: 'route'; route: HighRiskRoute; amended: string; original: string; tools: ToolDuties[] }
  /** Art. 111(2): duties that apply only after a significant change. */
  | { kind: 'afterChange'; tools: ToolDuties[] }

/** A high-risk provider's duties are summarised with a link to its own screen (P23). */
export function isProviderSummary(tool: CheckedTool): boolean {
  return tool.result.role === 'provider' && tool.result.risk_class === 'high_risk'
}

/** The result's class is assumed: its duties apply if the stricter reading holds. */
export function isAssumed(tool: CheckedTool): boolean {
  return tool.result.status !== 'decided'
}

/** The tools with a readable result, strictest class first. */
export function checkedTools(tools: readonly InventoryTool[]): CheckedTool[] {
  return sortTools(tools).filter(isChecked)
}

/** Minimal-risk and out-of-scope tools: no specific duties (decision 026 item 19). */
export function toolsWithoutDuties(tools: readonly CheckedTool[]): CheckedTool[] {
  return tools.filter(
    (tool) =>
      tool.result.risk_class === 'minimal_risk' || tool.result.risk_class === 'out_of_scope',
  )
}

/** A tool's duties; none for a tool out of the Act's scope, whatever its result lists. */
function dutiesOf(tool: CheckedTool): Obligation[] {
  return tool.result.risk_class === 'out_of_scope' ? [] : (tool.result.obligations ?? [])
}

/** Every tool with its duties, for By tool: a tool without any too, so By tool lists the same
 *  tools as By date (whose "No specific duties" section lists those). */
export function toolCards(tools: readonly CheckedTool[]): ToolDuties[] {
  return tools.map((tool) => ({ tool, duties: dutiesOf(tool) }))
}

type Slot =
  | { kind: 'stop' }
  | { kind: 'afterChange' }
  | { kind: 'route'; route: HighRiskRoute; amended: string }
  | { kind: 'dated'; date: string }

function slotOf(tool: CheckedTool, duty: Obligation): Slot {
  if (tool.result.risk_class === 'prohibited') return { kind: 'stop' }
  if (duty.legacy === 'legacy_unchanged') return { kind: 'afterChange' }
  const route = duty.high_risk_route
  if (route && duty.legacy !== 'legacy_public_authority') {
    return { kind: 'route', route, amended: duty.applies_from }
  }
  return { kind: 'dated', date: duty.applies_from }
}

/** A provider summary sits where its route's duties start (their Art. 111(2) slot when marked),
 *  or else with its first duty. */
function summarySlot(tool: CheckedTool, duties: readonly Obligation[]): Slot {
  const [first] = duties
  const dating = duties.find((duty) => duty.high_risk_route) ?? first
  return dating ? slotOf(tool, dating) : { kind: 'afterChange' }
}

function slotId(slot: Slot): string {
  switch (slot.kind) {
    case 'stop':
    case 'afterChange':
      return slot.kind
    case 'route':
      return `route:${slot.route}:${slot.amended}`
    case 'dated':
      return `dated:${slot.date}`
  }
}

/** The order of the sections: stop first, then by date (a route's by its amended date), then
 *  the duties waiting for a significant change. */
function slotRank(slot: Slot): [number, string] {
  switch (slot.kind) {
    case 'stop':
      return [0, '']
    case 'route':
      return [1, slot.amended]
    case 'dated':
      return [1, slot.date]
    case 'afterChange':
      return [2, '']
  }
}

const TRANSPARENCY_ARTICLE = 'art:50'

/** The article an article ID belongs to: `art:6:4` → `art:6`. */
function articleOf(article: string): string {
  return article.split(':').slice(0, 2).join(':')
}

/** What a dated section's duties are; `hasRouteTwin` when a route section has its date. */
function categoryOf(tools: readonly ToolDuties[], hasRouteTwin: boolean): SectionCategory | null {
  const articles = [...new Set(tools.flatMap(({ duties }) => duties.map((duty) => duty.article)))]
  const parents = [...new Set(articles.map(articleOf))]
  const [onlyArticle] = articles
  const [onlyParent] = parents
  if (parents.length === 1 && onlyParent === TRANSPARENCY_ARTICLE) return { kind: 'transparency' }
  if (articles.length === 1 && onlyArticle) return { kind: 'article', article: onlyArticle }
  if (parents.length === 1 && onlyParent) return { kind: 'article', article: onlyParent }
  return hasRouteTwin ? { kind: 'other' } : null
}

function toSection(
  slot: Slot,
  tools: ToolDuties[],
  today: Date,
  routeDays: ReadonlySet<string>,
): DateSection {
  switch (slot.kind) {
    case 'stop':
    case 'afterChange':
      return { kind: slot.kind, tools }
    case 'route':
      return { kind: 'route', route: slot.route, ...routeDates(slot.route, slot.amended), tools }
    case 'dated': {
      const hasRouteTwin = routeDays.has(slot.date)
      const dated = { date: slot.date, category: categoryOf(tools, hasRouteTwin), hasRouteTwin }
      return slot.date <= isoDay(today)
        ? { kind: 'since', ...dated, tools }
        : { kind: 'from', ...dated, tools }
    }
  }
}

type Bucket = { slot: Slot; tools: Map<string, ToolDuties> }

/** Puts the tool, and the duty if there is one, in the slot's bucket. */
function addTo(buckets: Map<string, Bucket>, slot: Slot, tool: CheckedTool, duty?: Obligation) {
  const id = slotId(slot)
  const bucket = buckets.get(id) ?? { slot, tools: new Map<string, ToolDuties>() }
  const entry = bucket.tools.get(tool.toolId) ?? { tool, duties: [] }
  bucket.tools.set(tool.toolId, { tool, duties: duty ? [...entry.duties, duty] : entry.duties })
  buckets.set(id, bucket)
}

/** By date: each duty in the section of the date it applies from, under its tool; a provider
 *  summary whole in one section; a prohibited tool under Stop now even without duties. */
export function dateSections(tools: readonly CheckedTool[], today: Date): DateSection[] {
  const buckets = new Map<string, Bucket>()
  for (const { tool, duties } of toolCards(tools)) {
    // Without duties only a prohibited tool is listed here, under Stop now; the others are in
    // "No specific duties" (`toolsWithoutDuties`).
    if (duties.length === 0 && tool.result.risk_class === 'prohibited') {
      addTo(buckets, { kind: 'stop' }, tool)
    }
    const summary = isProviderSummary(tool) ? summarySlot(tool, duties) : null
    for (const duty of duties) addTo(buckets, summary ?? slotOf(tool, duty), tool, duty)
  }
  const routeDays = new Set(
    [...buckets.values()].flatMap(({ slot }) => (slot.kind === 'route' ? [slot.amended] : [])),
  )
  return [...buckets.values()]
    .sort((a, b) => {
      const [rankA, dateA] = slotRank(a.slot)
      const [rankB, dateB] = slotRank(b.slot)
      return rankA - rankB || dateA.localeCompare(dateB)
    })
    .map((bucket) => toSection(bucket.slot, [...bucket.tools.values()], today, routeDays))
}

/** How many of the duties are ticked off, of those that can be. */
export type Progress = { done: number; total: number }

/** The keys ticked off on the tool. */
export function ticksOn(ticks: readonly DutyTick[], toolId: string): Set<string> {
  return new Set(ticks.filter((tick) => tick.toolId === toolId).map((tick) => tick.obligationKey))
}

/** The progress over these duties, given the keys ticked off on their tool (each key once). */
export function progressOver(duties: readonly Obligation[], done: ReadonlySet<string>): Progress {
  const keys = new Set(duties.map(tickKey).filter((key): key is string => key !== null))
  return { done: [...keys].filter((key) => done.has(key)).length, total: keys.size }
}

/** The progress over these duties of the tool (each key once). */
export function dutiesProgress(
  toolId: string,
  duties: readonly Obligation[],
  ticks: readonly DutyTick[],
): Progress {
  return progressOver(duties, ticksOn(ticks, toolId))
}

/** The tool's progress over all its duties. */
export function toolProgress(tool: CheckedTool, ticks: readonly DutyTick[]): Progress {
  return dutiesProgress(tool.toolId, dutiesOf(tool), ticks)
}

/** Every tool's progress added up. */
export function overallProgress(
  tools: readonly CheckedTool[],
  ticks: readonly DutyTick[],
): Progress {
  return tools
    .map((tool) => toolProgress(tool, ticks))
    .reduce((sum, next) => ({ done: sum.done + next.done, total: sum.total + next.total }), {
      done: 0,
      total: 0,
    })
}

/** The next date duties start under the law text on show: the earliest one still ahead, with the
 *  tools whose duties start then (a decided class first) and how many more might. */
export type NextDate = { date: string; tools: CheckedTool[]; assumed: number }

/** When a duty starts under `law`; null when it has no date to wait for (Art. 111(2) without a
 *  significant change, information, a prohibited tool's). */
function startOf(tool: CheckedTool, duty: Obligation, law: LawVersion): string | null {
  if (tool.result.risk_class === 'prohibited' || duty.is_informational) return null
  if (duty.legacy === 'legacy_unchanged') return null
  const route = duty.high_risk_route
  if (route && duty.legacy !== 'legacy_public_authority' && law === 'original') {
    return ORIGINAL_ROUTE_DATES[route]
  }
  return duty.applies_from
}

export function nextDate(
  tools: readonly CheckedTool[],
  today: Date,
  law: LawVersion,
): NextDate | null {
  const day = isoDay(today)
  const starts = tools.flatMap((tool) =>
    dutiesOf(tool)
      .map((duty) => startOf(tool, duty, law))
      .filter((date): date is string => date !== null && date > day)
      .map((date) => ({ tool, date })),
  )
  const [first] = starts.map((start) => start.date).sort()
  if (first === undefined) return null
  const starting = [
    ...new Map(
      starts.filter((start) => start.date === first).map(({ tool }) => [tool.toolId, tool]),
    ).values(),
  ]
  return {
    date: first,
    tools: starting.filter((tool) => !isAssumed(tool)),
    assumed: starting.filter(isAssumed).length,
  }
}
