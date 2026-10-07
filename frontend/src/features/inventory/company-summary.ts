import type { RiskClass } from '@/api'
import { isTransparencyDuty } from '@/features/classify/result-text'
import type { InventoryTool } from '@/lib/inventory'

import {
  ambiguousProvision,
  appliesFrom,
  CLASS_ORDER,
  isChecked,
  isoDay,
  openQuestionCount,
  type AppliesFrom,
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

/** The duties coming next: the tool whose duties start soonest, among those still ahead. */
export type NextDuties = {
  tool: CheckedTool
  appliesFrom: Extract<AppliesFrom, { kind: 'route' | 'from' }>
}

function startDate(applies: NextDuties['appliesFrom']): string {
  return applies.kind === 'route' ? applies.amended : applies.date
}

export function nextDuties(tools: readonly InventoryTool[], today: Date): NextDuties | null {
  const ahead = tools.filter(isChecked).flatMap((tool): NextDuties[] => {
    if (tool.result.risk_class === 'prohibited') return []
    const applies = appliesFrom(tool.result, today)
    return applies.kind === 'route' || applies.kind === 'from'
      ? [{ tool, appliesFrom: applies }]
      : []
  })
  return ahead.reduce<NextDuties | null>(
    (soonest, next) =>
      soonest === null || startDate(next.appliesFrom) < startDate(soonest.appliesFrom)
        ? next
        : soonest,
    null,
  )
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
