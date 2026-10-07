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

// Class and Status are never narrower than their widest pill, which stays on one line
// (components.md › InventoryTable). All six columns still fit the panel at 1280 px, in German
// too: the Tool column gives way (it takes the width left over, down to 160 px; its name wraps and
// its description truncates), and Basis and Applies from wrap between citations and words. Cells
// sit 12 px from their neighbours' edges: at 16 px the German table runs about 20 px past the panel.
const PILL_CELL = 'w-px whitespace-nowrap'
const TOOL_CELL = 'w-full min-w-40 max-w-0'
const CELL = 'px-3 py-3.5 align-middle text-body-small text-ink'
// The exceptions components.md allows: a class pill wider than its cap wraps inside the pill. In
// English the cap is 200 px and no class pill reaches it. In German it is 160 px, and two pills
// wrap: "Außerhalb des Anwendungsbereichs" (261 px on one line) and "Hochrisiko, angenommen"
// (190 px). 160 px is the narrowest two-line out-of-scope pill: "Anwendungsbereichs" alone needs it.
const CLASS_PILL_FIT = 'w-max max-w-[12.5rem] whitespace-normal [&:lang(de)]:max-w-[10rem]'
// A tool without a result says why in quiet text, not a pill: it wraps past 144 px ("Gespeichertes
// Ergebnis nicht lesbar") so its column stays as narrow as the widest status pill.
const QUIET_STATUS_FIT = 'inline-block w-max max-w-36 whitespace-normal text-slate'

function StatusCell({ row }: { row: InventoryRow }): JSX.Element {
  const { t } = useTranslation()
  // A decided row reads "Decided" as quiet text; open rows show their pill so they stand out.
  if (row.status === 'decided') {
    return <span className="text-slate">{t('status.decided')}</span>
  }
  if (row.status === null) return <span className={QUIET_STATUS_FIT}>{row.statusLabel}</span>
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
                  className="px-3 pt-5 pb-3 text-caption font-semibold whitespace-nowrap text-slate first:pl-7 last:pr-7"
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
                <td className={`${CELL} ${PILL_CELL}`}>
                  {row.riskClass ? (
                    <RiskPill
                      kind={row.riskClass}
                      label={row.classLabel}
                      className={CLASS_PILL_FIT}
                    />
                  ) : (
                    <span className="text-slate">{t('inventory.table.none')}</span>
                  )}
                </td>
                <td className={CELL}>{row.basis}</td>
                <td className={CELL}>{row.from}</td>
                <td className={`${CELL} ${PILL_CELL} pr-7`}>
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
