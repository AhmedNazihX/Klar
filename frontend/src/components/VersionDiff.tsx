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
  /** What the values are: a date or a reference (an Annex point) never breaks over two lines;
   *  text (a class, a role) wraps between words. Default text. */
  kind?: 'text' | 'date' | 'reference'
}

export type VersionDiffProps = {
  rows: readonly VersionDiffRow[]
  /** The two columns' headings; default "Original" and "Amended". */
  columns?: readonly [ReactNode, ReactNode]
  /** What changed and what didn't, naming the amending act. */
  note?: ReactNode
  className?: string
}

/** A row's cells sit straight in the grid (`contents`), so the columns line up across rows. */
const ROW = 'contents'
const CAPTION = 'text-caption font-normal text-slate'

/** The artboard's grid, `minmax(0,1fr) auto auto`, with the label kept to its longest word. */
const COLUMNS = 'grid-cols-[minmax(min-content,1fr)_auto_auto]'
/** Two references side by side don't fit a narrow panel (two German Annex points take about
 *  330 px): below 28rem each row stacks, its label above, each value on its own line after its
 *  column's name. Dates and words fit three columns at any width. */
const STACKED = {
  table: 'grid-cols-[auto_minmax(0,1fr)] @md:grid-cols-[minmax(min-content,1fr)_auto_auto]',
  header: '@max-md:sr-only',
  label: 'col-span-2 @md:col-span-1',
  cell: 'col-span-2 grid grid-cols-subgrid @md:col-span-1 @md:block',
  caption: '@md:hidden',
} as const

function Value({
  value,
  isChanged,
  isAfter,
}: {
  value: ReactNode
  isChanged: boolean
  isAfter: boolean
}): JSX.Element {
  if (!isChanged) return <span>{value}</span>
  if (isAfter) return <ins className="text-lens-blue no-underline">{value}</ins>
  return <del className="text-slate">{value}</del>
}

/**
 * What changes between the original Act and the amended one (components.md › VersionDiff): a
 * three-column comparison where only the changed values are struck through (before) and shown in
 * Lens blue (after). A table to assistive technology, with `del` and `ins`, so a screen reader
 * hears the change too. A date or an Annex point stays on one line; with an Annex point in it the
 * table stacks its rows in a narrow panel (a phone, the reviewer view's side column).
 */
export function VersionDiff({ rows, columns, note, className }: VersionDiffProps): JSX.Element {
  const { t } = useTranslation()
  const [before, after] = columns ?? [t('diff.original'), t('diff.amended')]
  const canStack = rows.some((row) => row.kind === 'reference')
  const stacked = canStack ? STACKED : null
  return (
    <div className={cn('@container flex flex-col gap-3.5', className)}>
      <div
        role="table"
        className={cn(
          'grid items-baseline gap-x-3 gap-y-2.5 text-[14px] leading-[1.35]',
          stacked?.table ?? COLUMNS,
        )}
      >
        <div role="rowgroup" className={ROW}>
          <div role="row" className={ROW}>
            <span className={stacked?.header} />
            <span role="columnheader" className={cn(CAPTION, stacked?.header)}>
              {before}
            </span>
            <span role="columnheader" className={cn(CAPTION, stacked?.header)}>
              {after}
            </span>
          </div>
        </div>
        <div role="rowgroup" className={ROW}>
          {rows.map((row) => {
            const isChanged = row.isChanged ?? row.before !== row.after
            const isWhole = row.kind === 'date' || row.kind === 'reference'
            const cells = [
              { key: 'before', heading: before, value: row.before, isAfter: false },
              { key: 'after', heading: after, value: row.after, isAfter: true },
            ]
            return (
              <div key={row.id} role="row" className={ROW}>
                <span role="rowheader" className={cn('text-ink', stacked?.label)}>
                  {row.label}
                </span>
                {cells.map((cell) => (
                  <span
                    key={cell.key}
                    role="cell"
                    className={cn('text-ink', cell.isAfter && 'font-semibold', stacked?.cell)}
                  >
                    {stacked && (
                      <span aria-hidden="true" className={cn(CAPTION, stacked.caption)}>
                        {cell.heading}
                      </span>
                    )}
                    <span className={cn(isWhole && 'whitespace-nowrap')}>
                      <Value value={cell.value} isChanged={isChanged} isAfter={cell.isAfter} />
                    </span>
                  </span>
                ))}
              </div>
            )
          })}
        </div>
      </div>
      {note && <p className="m-0 text-[13px] leading-normal text-slate">{note}</p>}
    </div>
  )
}
