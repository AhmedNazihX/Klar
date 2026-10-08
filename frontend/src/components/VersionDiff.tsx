import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

export type VersionDiffRow = {
  /** A stable key for the row, e.g. "class". */
  id: string
  label: ReactNode
  before: ReactNode
  after: ReactNode
  /** Whether the two values differ; by default, whether `before` and `after` are not equal. */
  isChanged?: boolean
}

export type VersionDiffProps = {
  rows: readonly VersionDiffRow[]
  /** The two columns' headings; default "Original" and "Amended". */
  columns?: readonly [ReactNode, ReactNode]
  /** What changed and what didn't, naming the amending act. */
  note?: ReactNode
  className?: string
}

/**
 * What changes between the original Act and the amended one (components.md › VersionDiff): a
 * three-column comparison where only the changed values are struck through (before) and shown in
 * Lens blue (after). A table, with `del` and `ins`, so a screen reader hears the change too.
 */
export function VersionDiff({ rows, columns, note, className }: VersionDiffProps): JSX.Element {
  const { t } = useTranslation()
  const [before, after] = columns ?? [t('diff.original'), t('diff.amended')]
  return (
    <div className={cn('flex flex-col gap-3.5', className)}>
      <table className="w-full border-separate border-spacing-x-3 border-spacing-y-2.5 text-[14px] leading-[1.35]">
        <thead>
          <tr>
            <td className="w-full p-0" />
            <th scope="col" className="p-0 text-left text-caption font-normal text-slate">
              {before}
            </th>
            <th scope="col" className="p-0 text-left text-caption font-normal text-slate">
              {after}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isChanged = row.isChanged ?? row.before !== row.after
            return (
              <tr key={row.id}>
                <th scope="row" className="p-0 text-left font-normal text-ink">
                  {row.label}
                </th>
                <td className="p-0 text-ink">
                  {isChanged ? (
                    <del className="text-slate">{row.before}</del>
                  ) : (
                    <span>{row.before}</span>
                  )}
                </td>
                <td className="p-0 font-semibold text-ink">
                  {isChanged ? (
                    <ins className="text-lens-blue no-underline">{row.after}</ins>
                  ) : (
                    <span>{row.after}</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {note && <p className="m-0 text-[13px] leading-normal text-slate">{note}</p>}
    </div>
  )
}
