import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { ScreenTitle } from '@/components/ScreenTitle'
import { SegmentedControl } from '@/components/SegmentedControl'
import type { CheckedTool } from '@/features/inventory/tool-facts'
import { useDutyTicks, useToggleDutyTick } from '@/hooks/use-duty-progress'
import { useInventoryTools } from '@/hooks/use-inventory-tools'
import { useLawVersion } from '@/hooks/use-law-version'
import type { DutyTick } from '@/lib/duty-progress'

import { DateSections, NoDutiesSection, ToolSections } from './DutySections'
import {
  checkedTools,
  dateSections,
  overallProgress,
  toolCards,
  toolsWithoutDuties,
} from './obligation-list'
import { ObligationsAside } from './ObligationsAside'
import type { TickHandler } from './ToolDutiesCard'

/** By date (the default) or By tool: shareable view state, kept in the address by the route. */
export type ObligationsGroup = 'date' | 'tool'

function GroupSwitch({
  group,
  onGroupChange,
}: {
  group: ObligationsGroup
  onGroupChange: (group: ObligationsGroup) => void
}): JSX.Element {
  const { t } = useTranslation()
  return (
    <SegmentedControl<ObligationsGroup>
      label={t('obligations.groupBy')}
      value={group}
      onChange={onGroupChange}
      options={[
        { value: 'date', label: t('obligations.byDate') },
        { value: 'tool', label: t('obligations.byTool') },
      ]}
    />
  )
}

function NoDutiesYet(): JSX.Element {
  const { t } = useTranslation()
  return (
    <GlassPanel className="flex flex-col items-center gap-2.5 px-5 py-10 text-center">
      <p className="m-0 text-body font-semibold text-ink">{t('obligations.empty.title')}</p>
      <p className="m-0 text-body-small text-slate">{t('obligations.empty.body')}</p>
      <Link to="/app/classify" className={buttonVariants({ className: 'mt-1.5' })}>
        {t('welcome.tools.classifyFirst')}
      </Link>
    </GlassPanel>
  )
}

/** The duty list in the chosen grouping; under the original text, the note that only the route
 *  dates swap (decision 026 item 11). */
function DutyList({
  tools,
  group,
  ticks,
  onTick,
  today,
}: {
  tools: readonly CheckedTool[]
  group: ObligationsGroup
  ticks: readonly DutyTick[]
  onTick: TickHandler
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const law = useLawVersion()
  const without = toolsWithoutDuties(tools)
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-5">
      <p className="m-0 text-body-small text-slate">{t('obligations.notChecked')}</p>
      {law === 'original' && (
        <p role="note" className="m-0 text-body-small text-ink-2">
          {t('result.todo.originalDates')}
        </p>
      )}
      {group === 'date' ? (
        <>
          <DateSections
            sections={dateSections(tools, today)}
            ticks={ticks}
            onTick={onTick}
            today={today}
          />
          {without.length > 0 && <NoDutiesSection tools={without} />}
        </>
      ) : (
        <ToolSections entries={toolCards(tools)} ticks={ticks} onTick={onTick} today={today} />
      )}
    </div>
  )
}

/**
 * The Obligations screen (artboard `Obligations`): every duty across the inventory, grouped By
 * date or By tool, each with a box the user ticks off (saved in duty_progress); beside it the
 * next date, the progress and the checklist download. The panels are the screen's direct
 * children, for the load motion; the AppFrame adds the notice.
 */
export function ObligationsScreen({
  today,
  group,
  onGroupChange,
}: {
  today: Date
  group: ObligationsGroup
  onGroupChange: (group: ObligationsGroup) => void
}): JSX.Element | null {
  const { t } = useTranslation()
  const tools = useInventoryTools()
  const ticks = useDutyTicks()
  const toggle = useToggleDutyTick()
  // A read that failed shows the screen's ErrorView (routes/app.tsx).
  if (tools.isError) throw tools.error
  if (ticks.isError) throw ticks.error
  // Without Supabase the queries never run: that inventory is empty, not loading.
  const isLoading =
    (tools.isPending && tools.fetchStatus === 'fetching') ||
    (ticks.isPending && ticks.fetchStatus === 'fetching')
  if (isLoading) return null
  const checked = checkedTools(tools.data ?? [])
  const saved = ticks.data ?? []
  const onTick: TickHandler = (tool, key, isDone) => {
    toggle.mutate({ toolId: tool.toolId, obligationKey: key, isDone })
  }
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <ScreenTitle>{t('screen.obligations')}</ScreenTitle>
          {checked.length > 0 && (
            <p className="m-0 text-body text-slate">
              {t(`obligations.intro.${group}`, { count: checked.length })}
            </p>
          )}
        </div>
        {checked.length > 0 && <GroupSwitch group={group} onGroupChange={onGroupChange} />}
      </div>
      {toggle.isError && (
        <p role="alert" className="m-0 text-body-small text-risk-prohibited">
          {t('obligations.saveFailed')}
        </p>
      )}
      {checked.length === 0 ? (
        <NoDutiesYet />
      ) : (
        <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
          <DutyList tools={checked} group={group} ticks={saved} onTick={onTick} today={today} />
          <ObligationsAside
            tools={checked}
            ticks={saved}
            progress={overallProgress(checked, saved)}
            today={today}
          />
        </div>
      )}
    </>
  )
}
