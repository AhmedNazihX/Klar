import type { RiskClass } from '@/api'
import type { LawVersion } from '@/components/LawSwitch'
import { isTransparencyDuty } from '@/features/classify/result-text'
import type { InventoryTool } from '@/lib/inventory'

import {
  ambiguousProvision,
  appliesFrom,
  CLASS_ORDER,
  isChecked,
  isoDay,
  openQuestionCount,
  type CheckedTool,
} from './tool-facts'

// The company-level view of the inventory (artboard `Inventory`): counts per class, what needs
// the user, the next duties and the duties already in force. An assumed result (needs more
// information, legally ambiguous) counts in the stricter class it was given and is flagged as
// assumed: it never settles the lenient way.

export type ClassCount = { riskClass: RiskClass; total: number; assumed: number }

/** Tools per class, strictest first, with how many of them are assumed. */
export function classCounts(tools: readonly InventoryTool[]): ClassCount[] {
  const checked = tools.filter(isChecked)
  return CLASS_ORDER.map((riskClass) => {
    const inClass = checked.filter((tool) => tool.result.risk_class === riskClass)
    return {
      riskClass,
      total: inClass.length,
      assumed: inClass.filter((tool) => tool.result.status !== 'decided').length,
    }
  })
}

/** Something a tool needs from the user, with its action. */
export type NeedsYou =
  | { kind: 'prohibited'; tool: CheckedTool }
  | { kind: 'needs-info'; tool: CheckedTool; questions: number }
  | { kind: 'ambiguous'; tool: CheckedTool; provision: string | null }

function needOf(tool: CheckedTool): NeedsYou | null {
  const { result } = tool
  if (result.risk_class === 'prohibited') return { kind: 'prohibited', tool }
  if (result.status === 'needs_more_information') {
    return { kind: 'needs-info', tool, questions: openQuestionCount(result) }
  }
  if (result.status === 'legally_ambiguous') {
    return { kind: 'ambiguous', tool, provision: ambiguousProvision(result) }
  }
  return null
}

const NEED_ORDER: readonly NeedsYou['kind'][] = ['prohibited', 'needs-info', 'ambiguous']

/** "N tools need you": prohibited tools first, then paused results, then ambiguous ones. */
export function toolsNeedingYou(tools: readonly InventoryTool[]): NeedsYou[] {
  const needs = tools
    .filter(isChecked)
    .map(needOf)
    .filter((need): need is NeedsYou => need !== null)
  return NEED_ORDER.flatMap((kind) => needs.filter((need) => need.kind === kind))
}

/** The prohibited tools the summary sentence opens with: how many, how many of them are assumed,
 *  and the one it names when there is only one (a decided one before an assumed one). */
export type ProhibitedTools = { named: CheckedTool; total: number; assumed: number }

export function prohibitedTools(tools: readonly InventoryTool[]): ProhibitedTools | null {
  const prohibited = tools
    .filter(isChecked)
    .filter((tool) => tool.result.risk_class === 'prohibited')
  const assumed = prohibited.filter((tool) => tool.result.status !== 'decided')
  const named = prohibited.find((tool) => tool.result.status === 'decided') ?? prohibited[0]
  return named ? { named, total: prohibited.length, assumed: assumed.length } : null
}

/**
 * The duties the summary sentence names: the tool whose duties start soonest under the law text
 * on show, or, when every such date has come (the route's 2024 date under the original text),
 * the one whose duties applied last. A decided result is preferred: an assumed one is named only
 * when no decided one has dated duties, and the sentence then says its class is assumed.
 */
export type NextDuties = {
  tool: CheckedTool
  /** The date under the law text on show (ISO). */
  date: string
  /** The date has come: the duties already apply. */
  isInForce: boolean
  /** The tool's class is assumed (needs more information, legally ambiguous). */
  isAssumed: boolean
}

/** The date a tool's dated duties start under `law`; null when they have none to name. */
function dutiesStart(tool: CheckedTool, today: Date, law: LawVersion): string | null {
  if (tool.result.risk_class === 'prohibited') return null
  const applies = appliesFrom(tool.result, today)
  if (applies.kind === 'route') return law === 'original' ? applies.original : applies.amended
  return applies.kind === 'from' ? applies.date : null
}

function pick(dated: readonly NextDuties[]): NextDuties | null {
  const ahead = dated.filter((next) => !next.isInForce)
  if (ahead.length > 0) {
    return ahead.reduce((soonest, next) => (next.date < soonest.date ? next : soonest))
  }
  return dated.reduce<NextDuties | null>(
    (latest, next) => (latest === null || next.date > latest.date ? next : latest),
    null,
  )
}

export function nextDuties(
  tools: readonly InventoryTool[],
  today: Date,
  law: LawVersion = 'amended',
): NextDuties | null {
  const day = isoDay(today)
  const dated = tools.filter(isChecked).flatMap((tool): NextDuties[] => {
    const date = dutiesStart(tool, today, law)
    if (date === null) return []
    const isAssumed = tool.result.status !== 'decided'
    return [{ tool, date, isInForce: date <= day, isAssumed }]
  })
  return pick(dated.filter((next) => !next.isAssumed)) ?? pick(dated)
}

/** The Art. 50 transparency duties already in force: how many tools have one, and since when. */
export type TransparencyInForce = { tools: number; since: string }

export function transparencyInForce(
  tools: readonly InventoryTool[],
  today: Date,
): TransparencyInForce | null {
  const day = isoDay(today)
  const dates = tools.filter(isChecked).flatMap((tool) => {
    const inForce = (tool.result.obligations ?? [])
      .filter((duty) => isTransparencyDuty(duty) && !duty.is_informational)
      .map((duty) => duty.applies_from)
      .filter((date) => date <= day)
      .sort()
    const [since] = inForce
    return since ? [since] : []
  })
  if (dates.length === 0) return null
  const [since] = [...dates].sort()
  return since ? { tools: dates.length, since } : null
}

/** The consolidation date every result was checked against, when they all share one (amended
 *  text); null when they differ, any is on the original text or no tool has a result. */
export function sharedLawDate(tools: readonly InventoryTool[]): string | null {
  const checked = tools.filter(isChecked)
  if (checked.length === 0 || checked.length !== tools.length) return null
  const dates = new Set(
    checked.map((tool) =>
      tool.result.law_version === 'amended' ? tool.result.law_text?.version_date : undefined,
    ),
  )
  const [only] = dates
  return dates.size === 1 && only ? only : null
}
