import type { TFunction } from 'i18next'
import { Fragment, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { InventoryTable, type InventoryRow } from '@/components/InventoryTable'
import { LawDate } from '@/components/LawDate'
import { shortDate } from '@/features/classify/dates'
import { statusPill, toolName } from '@/features/classify/result-text'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'
import type { InventoryTool } from '@/lib/inventory'

import { appliesFrom, basisReferences, whatItDoes, type AppliesFrom } from './tool-facts'

/** The Art. 111(2) tag beside a legacy-marked date (decision 026 item 24). */
function LegacyTag({ children }: { children: ReactNode }): JSX.Element {
  return (
    <span className="ml-2 inline-flex h-[22px] items-center rounded-tag bg-white/60 px-2 text-xs font-semibold whitespace-nowrap text-ink-2 shadow-[inset_0_0_0_1px_var(--color-border-subtle)]">
      {children}
    </span>
  )
}

const DATE_MARK = '§DATE§'

/**
 * A translated line around a date ("Seit dem 2. Aug. 2026"): the words wrap like prose, the date
 * itself never breaks ("2. Aug. / 2026" is not allowed).
 */
function datedLine(line: (date: string) => string, isoDate: string, language: Language): ReactNode {
  const [before = '', after = ''] = line(DATE_MARK).split(DATE_MARK)
  return (
    <>
      {before}
      <span data-date className="whitespace-nowrap">
        {shortDate(isoDate, language)}
      </span>
      {after}
    </>
  )
}

// The Art. 111(2) lines wrap like prose, with the tag kept whole: the column gives way rather
// than pushing the table past its panel.
function appliesFromCell(t: TFunction, applies: AppliesFrom, language: Language): ReactNode {
  switch (applies.kind) {
    case 'none':
      return t('inventory.table.none')
    case 'route':
      // The route's dates follow the law version switch (decision 026 item 11).
      return (
        <LawDate
          className="whitespace-nowrap"
          amended={shortDate(applies.amended, language)}
          original={shortDate(applies.original, language)}
        />
      )
    case 'from':
      return datedLine((date) => t('inventory.table.from', { date }), applies.date, language)
    case 'since':
      return datedLine((date) => t('inventory.table.since', { date }), applies.date, language)
    case 'afterChange':
      return (
        <>
          {t('result.legacy.afterChange')}
          <LegacyTag>{t('result.legacy.tag')}</LegacyTag>
        </>
      )
    case 'legacyFrom':
      return (
        <>
          {datedLine((date) => t('result.legacy.from', { date }), applies.date, language)}
          <LegacyTag>{t('result.legacy.tag')}</LegacyTag>
        </>
      )
  }
}

/** The Basis column: each citation stays whole on its line; lines break only between them. */
function basisCell(t: TFunction, result: ClassificationResult, language: Language): ReactNode {
  if (result.risk_class === 'minimal_risk') return t('inventory.table.noDuty')
  const references = basisReferences(result, language)
  if (references.length === 0) return t('inventory.table.none')
  return references.map((reference, position) => (
    <Fragment key={reference}>
      {position > 0 && ', '}
      <span className="whitespace-nowrap">{reference}</span>
    </Fragment>
  ))
}

function checkedRow(
  t: TFunction,
  tool: InventoryTool,
  result: ClassificationResult,
  language: Language,
  today: Date,
): InventoryRow {
  const isAssumed = result.status !== 'decided'
  return {
    toolId: tool.toolId,
    name: toolName(t, tool.name),
    what: whatItDoes(tool),
    role: result.role ? t(`result.roleName.${result.role}`) : t('inventory.table.none'),
    riskClass: result.risk_class,
    // An open result keeps the stricter class it was given, and says it is assumed.
    classLabel: isAssumed
      ? t('inventory.table.assumedClass', { riskClass: t(`pill.${result.risk_class}`) })
      : undefined,
    basis: basisCell(t, result, language),
    from: appliesFromCell(t, appliesFrom(result, today), language),
    status: statusPill(result.status),
  }
}

function toRow(t: TFunction, tool: InventoryTool, language: Language, today: Date): InventoryRow {
  if (tool.result) return checkedRow(t, tool, tool.result, language, today)
  const none = t('inventory.table.none')
  return {
    toolId: tool.toolId,
    name: toolName(t, tool.name),
    what: whatItDoes(tool),
    role: none,
    riskClass: null,
    basis: none,
    from: none,
    status: null,
    statusLabel: tool.hasUnreadableResult
      ? t('inventory.table.unreadable')
      : t('inventory.table.unchecked'),
  }
}

/** The inventory's table: one row per tool (already in the screen's order), each linking to its
 *  own result. */
export function ToolsTable({
  tools,
  today,
}: {
  tools: readonly InventoryTool[]
  today: Date
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  return (
    <InventoryTable
      label={t('inventory.table.label')}
      rows={tools.map((tool) => toRow(t, tool, language, today))}
    />
  )
}
