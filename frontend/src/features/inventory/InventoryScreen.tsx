import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import { ScreenTitle } from '@/components/ScreenTitle'
import { longDate } from '@/features/classify/dates'
import { ImportDataButton } from '@/features/welcome/ImportDataButton'
import { useInventoryTools } from '@/hooks/use-inventory-tools'
import { useLanguage } from '@/hooks/use-language'
import type { InventoryTool } from '@/lib/inventory'

import { sharedLawDate, toolsNeedingYou } from './company-summary'
import { CompanySummary } from './CompanySummary'
import { NeedsYouPanel } from './NeedsYouPanel'
import { sortTools } from './tool-facts'
import { ToolsTable } from './ToolsTable'

function CountLine({ tools }: { tools: readonly InventoryTool[] }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const lawDate = sharedLawDate(tools)
  return (
    <p className="m-0 text-body text-slate">
      {lawDate
        ? t('inventory.count', { count: tools.length, date: longDate(lawDate, language) })
        : t('inventory.countPlain', { count: tools.length })}
    </p>
  )
}

/** Tools are added one at a time through Classify, or restored from an exported file. */
function AddTool(): JSX.Element {
  const { t } = useTranslation()
  return (
    <Link to="/app/classify" className={buttonVariants()}>
      <Icon name="add" size={16} />
      {t('inventory.add')}
    </Link>
  )
}

function EmptyInventory(): JSX.Element {
  const { t } = useTranslation()
  return (
    <GlassPanel className="flex flex-col items-center gap-2.5 px-5 py-10 text-center">
      <span className="flex size-11 items-center justify-center rounded-item bg-lens-blue-soft text-lens-blue">
        <Icon name="inventory" />
      </span>
      <p className="m-0 text-body font-semibold text-ink">{t('welcome.tools.emptyTitle')}</p>
      <p className="m-0 text-body-small text-slate">{t('welcome.tools.emptyBody')}</p>
      <Link to="/app/classify" className={buttonVariants({ className: 'mt-1.5' })}>
        {t('welcome.tools.classifyFirst')}
      </Link>
    </GlassPanel>
  )
}

function InventoryContent({
  tools,
  today,
}: {
  tools: readonly InventoryTool[]
  today: Date
}): JSX.Element {
  const needs = toolsNeedingYou(tools)
  return (
    <>
      <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
        <CompanySummary tools={tools} today={today} />
        {needs.length > 0 && <NeedsYouPanel needs={needs} />}
      </div>
      <ToolsTable tools={sortTools(tools)} today={today} />
    </>
  )
}

/**
 * The AI inventory (artboard `Inventory`): the title with the tool count, "Import your data" and
 * "Add a tool"; then the company summary beside the tools that need the user, and the table of
 * every tool (the AppFrame adds the notice). The panels are the screen's direct children, for the
 * load motion.
 */
export function InventoryScreen({ today }: { today: Date }): JSX.Element {
  const { t } = useTranslation()
  const tools = useInventoryTools()
  // A read that failed shows the screen's ErrorView (routes/app.tsx).
  if (tools.isError) throw tools.error
  const list = tools.data ?? []
  // Without Supabase the query never runs: that inventory is empty, not loading.
  const isLoading = tools.isPending && tools.fetchStatus === 'fetching'
  let content: JSX.Element | null = <EmptyInventory />
  if (isLoading) content = null
  else if (list.length > 0) content = <InventoryContent tools={list} today={today} />
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <ScreenTitle>{t('screen.inventory')}</ScreenTitle>
          {list.length > 0 && <CountLine tools={list} />}
        </div>
        <div className="flex flex-wrap items-start gap-3">
          <ImportDataButton />
          <AddTool />
        </div>
      </div>
      {content}
    </>
  )
}
