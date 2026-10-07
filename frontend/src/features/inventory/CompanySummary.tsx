import type { TFunction } from 'i18next'
import type { JSX } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import type { RiskClass } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { longDate, shortDate } from '@/features/classify/dates'
import { toolName } from '@/features/classify/result-text'
import { useLanguage } from '@/hooks/use-language'
import { useLawVersion } from '@/hooks/use-law-version'
import type { InventoryTool } from '@/lib/inventory'
import { cn } from '@/lib/utils'

import {
  classCounts,
  nextDuties,
  prohibitedTools,
  transparencyInForce,
  type ClassCount,
  type NextDuties,
  type ProhibitedTools,
} from './company-summary'

const DOT_CLASS: Record<RiskClass, string> = {
  prohibited: 'bg-risk-prohibited-dot',
  high_risk: 'bg-risk-high-dot',
  limited_risk: 'bg-risk-limited-dot',
  minimal_risk: 'bg-risk-minimal-dot',
  out_of_scope: 'bg-risk-out-dot',
}

/** "Call mood scoring is prohibited…", saying when that is assumed (one tool: its class; several:
 *  how many of them). */
function prohibitedSentence(t: TFunction, prohibited: ProhibitedTools): string {
  const sentence = t('inventory.summary.prohibited', {
    count: prohibited.total,
    name: toolName(t, prohibited.named.name),
  })
  if (prohibited.assumed === 0) return sentence
  const assumed =
    prohibited.total === 1
      ? t('inventory.summary.assumedClass', { riskClass: t('pill.prohibited') })
      : t('inventory.summary.prohibitedAssumed', { count: prohibited.assumed })
  return `${sentence} ${assumed}`
}

/** "One tool is prohibited…", then the duties coming next (or already applying) under the law
 *  text on show. */
function SummarySentence({
  tools,
  next,
}: {
  tools: readonly InventoryTool[]
  next: NextDuties | null
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const prohibited = prohibitedTools(tools)
  return (
    <p className="m-0 max-w-[620px] text-body-large text-ink">
      {prohibited && <>{prohibitedSentence(t, prohibited)} </>}
      {next && (
        <>
          {/* The name goes in as an element, never into the string Trans parses for tags. */}
          <Trans
            i18nKey={`inventory.summary.${next.isInForce ? 'since' : 'next'}.${next.tool.result.role ?? 'none'}`}
            components={{
              name: <span>{toolName(t, next.tool.name)}</span>,
              date: <span>{longDate(next.date, language)}</span>,
            }}
          />
          {next.isAssumed &&
            ` ${t('inventory.summary.assumedClass', { riskClass: t(`pill.${next.tool.result.risk_class}`) })}`}
        </>
      )}
      {!prohibited && !next && t('inventory.summary.calm')}
    </p>
  )
}

/** The counts per class as a bar and a legend; assumed results are counted in their stricter
 *  class and flagged. */
function ClassCounts({ counts }: { counts: readonly ClassCount[] }): JSX.Element {
  const { t } = useTranslation()
  const shown = counts.filter((count) => count.total > 0)
  return (
    <div className="flex flex-col gap-3">
      <div aria-hidden="true" className="flex h-2.5 overflow-hidden rounded-pill bg-white/50">
        {shown.map((count) => (
          <div
            key={count.riskClass}
            className={DOT_CLASS[count.riskClass]}
            style={{ flexGrow: count.total }}
          />
        ))}
      </div>
      <ul
        aria-label={t('inventory.summary.countsLabel')}
        className="m-0 flex list-none flex-wrap gap-x-5 gap-y-2 p-0 text-body-small text-ink"
      >
        {shown.map((count) => (
          <li key={count.riskClass} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className={cn('size-2 shrink-0 rounded-full', DOT_CLASS[count.riskClass])}
            />
            <b>{count.total}</b> {t(`pill.${count.riskClass}`)}
            {count.assumed > 0 && (
              <span className="text-slate">
                ({t('inventory.summary.assumedCount', { count: count.assumed })})
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** "Already in force": the Art. 50 transparency duties that already apply. */
function InForceBox({
  tools,
  today,
}: {
  tools: readonly InventoryTool[]
  today: Date
}): JSX.Element | null {
  const { t } = useTranslation()
  const language = useLanguage()
  const transparency = transparencyInForce(tools, today)
  if (!transparency) return null
  return (
    <div className="flex min-w-[200px] flex-col gap-1 rounded-card-small px-4 py-3 glass-thin">
      <p className="m-0 text-caption text-slate">{t('inventory.summary.inForce')}</p>
      <p className="m-0 text-body-small font-semibold text-ink">
        {t('inventory.summary.transparency', { count: transparency.tools })}
      </p>
      <p className="m-0 text-caption text-slate">
        {t('inventory.summary.transparencySince', {
          date: shortDate(transparency.since, language),
        })}
      </p>
    </div>
  )
}

/**
 * The company summary (artboard `Inventory`): a sentence on what comes first, the duties already
 * in force, the tools per class. The results are what the browser stored (P3), so the panel says
 * it sums them up and doesn't present them as a verified record.
 */
export function CompanySummary({
  tools,
  today,
}: {
  tools: readonly InventoryTool[]
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const law = useLawVersion()
  const counts = classCounts(tools)
  const assumed = counts.reduce((sum, count) => sum + count.assumed, 0)
  return (
    <GlassPanel
      as="section"
      aria-label={t('inventory.summary.heading')}
      className="flex min-w-0 flex-1 flex-col gap-5 px-7 py-6.5"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 flex-col gap-2">
          <h2 className="m-0 text-caption text-slate">{t('inventory.summary.heading')}</h2>
          <SummarySentence tools={tools} next={nextDuties(tools, today, law)} />
        </div>
        <InForceBox tools={tools} today={today} />
      </div>
      <ClassCounts counts={counts} />
      {assumed > 0 && (
        <p className="m-0 text-body-small text-ink-2">
          {t('inventory.summary.assumedNote', { count: assumed })}
        </p>
      )}
      <p className="m-0 text-caption text-slate">{t('inventory.summary.source')}</p>
    </GlassPanel>
  )
}
