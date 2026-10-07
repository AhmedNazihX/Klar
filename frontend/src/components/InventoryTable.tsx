import { Link } from '@tanstack/react-router'
import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { RiskClass } from '@/api'

import { GlassPanel } from './GlassPanel'
import { RiskPill } from './RiskPill'
import { StatusPill } from './StatusPill'

export type InventoryRow = {
  toolId: string
  name: string
  /** What the tool does, one line; it truncates rather than wraps. */
  what: string
  role: ReactNode
  /** Null while the tool has no class to show (not checked yet, or its result can't be read). */
  riskClass: RiskClass | null
  /** The pill's label when it isn't the plain class, e.g. "High-risk, assumed". */
  classLabel?: string
  basis: ReactNode
  from: ReactNode
  /** Null with a `statusLabel` for a tool without a result. */
  status: 'decided' | 'ambiguous' | 'needs-info' | null
  statusLabel?: string
}

export type InventoryTableProps = {
  rows: readonly InventoryRow[]
  /** The table's accessible name. */
  label: string
}

const HEADINGS = ['tool', 'role', 'class', 'basis', 'appliesFrom', 'status'] as const

// All six columns fit the panel, in German too: the Tool column gives way first (it takes the
// width left over, its name wraps and its description truncates), then a long pill or an
// Art. 111(2) date wraps inside its cell rather than pushing Status out of the panel.
const TOOL_CELL = 'w-full min-w-[160px] max-w-0'
const CELL = 'px-4 py-3.5 align-middle text-body-small text-ink'

function StatusCell({ row }: { row: InventoryRow }): JSX.Element {
  const { t } = useTranslation()
  // A decided row reads "Decided" as quiet text; open rows show their pill so they stand out.
  if (row.status === 'decided') {
    return <span className="text-slate">{t('status.decided')}</span>
  }
  if (row.status === null) return <span className="text-slate">{row.statusLabel}</span>
  return <StatusPill status={row.status} size="sm" />
}

/**
 * Every AI tool in one glass table (components.md › InventoryTable): the tool and what it does,
 * the company's role, the class, the basis, the date duties apply from and the status. Each row
 * links to the tool's own result: the name is the link, and it covers the whole row.
 */
export function InventoryTable({ rows, label }: InventoryTableProps): JSX.Element {
  const { t } = useTranslation()
  return (
    <GlassPanel as="section" aria-label={label} padded={false} className="min-w-0">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">{label}</caption>
          <thead>
            <tr className="border-b border-border-subtle">
              {HEADINGS.map((heading) => (
                <th
                  key={heading}
                  scope="col"
                  className="px-4 pt-5 pb-3 text-caption font-semibold whitespace-nowrap text-slate first:pl-7 last:pr-7"
                >
                  {t(`inventory.table.${heading}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.toolId}
                // The link covers the row, so the row shows its keyboard focus.
                className="relative border-b border-border-subtle last:border-b-0 hover:bg-white/40 has-[a:focus-visible]:bg-white/40 has-[a:focus-visible]:outline-2 has-[a:focus-visible]:-outline-offset-2 has-[a:focus-visible]:outline-lens-blue"
              >
                <td className={`${CELL} ${TOOL_CELL} pl-7`}>
                  <Link
                    to="/app/inventory/$toolId"
                    params={{ toolId: row.toolId }}
                    className="block font-semibold break-words text-ink after:absolute after:inset-0 after:content-[''] focus-visible:outline-none"
                  >
                    {row.name}
                  </Link>
                  <span className="block truncate text-caption text-slate">{row.what}</span>
                </td>
                <td className={`${CELL} whitespace-nowrap`}>{row.role}</td>
                <td className={CELL}>
                  {row.riskClass ? (
                    <RiskPill kind={row.riskClass} label={row.classLabel} />
                  ) : (
                    <span className="text-slate">{t('inventory.table.none')}</span>
                  )}
                </td>
                <td className={CELL}>{row.basis}</td>
                <td className={CELL}>{row.from}</td>
                <td className={`${CELL} pr-7`}>
                  <StatusCell row={row} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassPanel>
  )
}
