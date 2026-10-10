import { Link } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { useState, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Obligation } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'
import { DutyItem } from '@/features/classify/DutyItem'
import { dutyNote, statusPill, toolName } from '@/features/classify/result-text'
import { longDate } from '@/features/classify/dates'
import { isoDay, type CheckedTool } from '@/features/inventory/tool-facts'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'
import { tickKey } from '@/lib/duty-progress'
import { riskClassOf } from '@/lib/risk-class'

import { isAssumed, isProviderSummary, type Progress } from './obligation-list'

/** How many duties a card shows before "Show all". */
export const DUTY_PREVIEW = 4

export type TickHandler = (tool: CheckedTool, key: string, isDone: boolean) => void

function CardHeader({ tool, progress }: { tool: CheckedTool; progress: Progress }): JSX.Element {
  const { t } = useTranslation()
  const { result } = tool
  const riskClass = riskClassOf(result)
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <Link
        to="/app/inventory/$toolId"
        params={{ toolId: tool.toolId }}
        className="min-w-0 text-body font-semibold break-words text-ink no-underline hover:underline"
      >
        {toolName(t, tool.name)}
      </Link>
      {result.role && (
        <span className="text-caption text-slate">{t(`result.roleName.${result.role}`)}</span>
      )}
      <span className="grow" />
      {progress.total > 0 && (
        <span className="text-caption font-semibold whitespace-nowrap text-ink-2">
          {t('obligations.card.done', progress)}
        </span>
      )}
      {isAssumed(tool) && <StatusPill status={statusPill(result.status)} size="sm" />}
      <RiskPill
        kind={riskClass}
        label={
          isAssumed(tool)
            ? t('inventory.table.assumedClass', { riskClass: t(`pill.${riskClass}`) })
            : undefined
        }
      />
    </div>
  )
}

/** The line under a duty. A prohibited tool's duty that only starts later (Art. 5(1)(ba) and
 *  (bb), from 2 December 2026) says from when, so it never reads as banned today. */
function noteOf(
  t: TFunction,
  tool: CheckedTool,
  duty: Obligation,
  language: Language,
  today: Date,
): ReactNode {
  const note = dutyNote(t, duty, language)
  const isLater = tool.result.risk_class === 'prohibited' && duty.applies_from > isoDay(today)
  if (!isLater) return note
  const from = t('obligations.card.from', { date: longDate(duty.applies_from, language) })
  return note ? (
    <>
      <span>{from}</span>
      <span>{note}</span>
    </>
  ) : (
    from
  )
}

/** "Show all 7 duties" when every line can be ticked, so it matches the card's "N of 7 done";
 *  else "Show 1 more", which can't be read as that count. */
function showAllLabel(t: TFunction, duties: readonly Obligation[]): string {
  const isEveryLineTickable = duties.every((duty) => tickKey(duty) !== null)
  return isEveryLineTickable
    ? t('obligations.card.showAll', { count: duties.length })
    : t('obligations.card.showMore', { count: duties.length - DUTY_PREVIEW })
}

function DutyList({
  tool,
  duties,
  done,
  onTick,
  today,
}: {
  tool: CheckedTool
  duties: readonly Obligation[]
  done: ReadonlySet<string>
  onTick: TickHandler
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const [isOpen, setIsOpen] = useState(false)
  const shown = isOpen ? duties : duties.slice(0, DUTY_PREVIEW)
  return (
    <>
      <ul className="m-0 flex list-none flex-col p-0">
        {shown.map((duty) => (
          <DutyItem
            key={duty.key ?? `${duty.article}:${duty.duty}`}
            duty={duty}
            toolId={tool.toolId}
            note={noteOf(t, tool, duty, language, today)}
            docLabel={t('obligations.card.draftReady')}
            done={done}
            onTick={(key, isDone) => onTick(tool, key, isDone)}
          />
        ))}
      </ul>
      {duties.length > DUTY_PREVIEW && (
        <button
          type="button"
          aria-expanded={isOpen}
          onClick={() => setIsOpen(!isOpen)}
          className="self-start border-0 bg-transparent p-0 text-label text-lens-blue hover:underline focus-visible:outline-2 focus-visible:outline-lens-blue"
        >
          {isOpen ? t('obligations.card.showFewer') : showAllLabel(t, duties)}
        </button>
      )}
    </>
  )
}

/** A high-risk provider's duties in one line, with a link to its own screen (P23). */
function ProviderSummary({ tool, total }: { tool: CheckedTool; total: number }): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <p className="m-0 text-body-small text-slate">
        {t('obligations.card.provider', { count: total })}
      </p>
      <Link
        to="/app/inventory/$toolId"
        params={{ toolId: tool.toolId }}
        className="self-start text-label text-lens-blue no-underline hover:underline"
      >
        {t('obligations.card.openProvider')}
      </Link>
    </>
  )
}

/**
 * One tool's duties in a section (artboard `Obligations`): its name, role, "N of M done" and
 * class; a prohibited tool says to stop first, an assumed class says its duties apply if the
 * stricter reading holds; then its duties with their ticks, the first few until "Show all", or
 * a high-risk provider's summary; a tool without duties (minimal risk, out of scope) says so.
 * The count is over the duties the card lists.
 */
export function ToolDutiesCard({
  tool,
  duties,
  progress,
  done,
  onTick,
  today,
}: {
  tool: CheckedTool
  duties: readonly Obligation[]
  progress: Progress
  done: ReadonlySet<string>
  onTick: TickHandler
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const { result } = tool
  return (
    <GlassPanel tone="thin" radius="small" padded={false} className="flex flex-col gap-3 px-5 py-4">
      <CardHeader tool={tool} progress={progress} />
      {result.risk_class === 'prohibited' && (
        <p className="m-0 text-body-small font-medium text-risk-prohibited">
          {t('inventory.needs.prohibited')}
        </p>
      )}
      {result.status !== 'decided' && (
        <p className="m-0 text-body-small text-ink-2">
          {t(`obligations.card.stricter.${result.status}`)}
        </p>
      )}
      {duties.length === 0 && result.risk_class !== 'prohibited' && (
        <p className="m-0 text-body-small text-slate">{t('obligations.card.noDuties')}</p>
      )}
      {isProviderSummary(tool) ? (
        <ProviderSummary tool={tool} total={progress.total} />
      ) : (
        duties.length > 0 && (
          <DutyList tool={tool} duties={duties} done={done} onTick={onTick} today={today} />
        )
      )}
    </GlassPanel>
  )
}
