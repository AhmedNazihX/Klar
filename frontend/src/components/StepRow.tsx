import { useId, type CSSProperties, type JSX, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

import { Icon } from './Icon'

/** The row's columns in English; German citations need 220 / 280 px (localisation.md). */
export const STEP_COLUMNS_EN = '180px minmax(0,1fr) 200px 20px'
export const STEP_COLUMNS_DE = '220px minmax(0,1fr) 280px 20px'

export type StepRowProps = {
  name: ReactNode
  decision: ReactNode
  reference: ReactNode
  expanded: boolean
  onToggle: (expanded: boolean) => void
  /** The grid from 768 px up; below it the row stacks. */
  columns?: string
  /** The expanded step, shown under the row. */
  children?: ReactNode
}

/**
 * One step of the classification, collapsed: its name, a one-line decision and the provision it
 * rests on. Expanding it shows the step in full (its StepCard). A reference never truncates:
 * it wraps between references, never inside one.
 */
export function StepRow({
  name,
  decision,
  reference,
  expanded,
  onToggle,
  columns = STEP_COLUMNS_EN,
  children,
}: StepRowProps): JSX.Element {
  const panelId = useId()
  return (
    <div className="border-t border-hairline">
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={() => {
          onToggle(!expanded)
        }}
        style={{ '--step-columns': columns } as CSSProperties}
        className="grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_20px] items-center gap-x-4 gap-y-1 rounded-item border-0 bg-transparent px-2 py-3 text-left text-body-small md:grid-cols-(--step-columns)"
      >
        <span className="font-semibold text-ink">{name}</span>
        <span className="col-start-1 text-ink-2 md:col-start-auto">{decision}</span>
        <span className="col-start-1 text-caption font-normal text-slate md:col-start-auto md:text-right">
          {reference}
        </span>
        <Icon
          name="chevron-down"
          size={18}
          className={cn(
            'col-start-2 row-start-1 text-slate transition-transform duration-300 md:col-start-auto md:row-start-auto',
            expanded && 'rotate-180',
          )}
        />
      </button>
      <div id={panelId} hidden={!expanded} className="pb-3">
        {expanded && children}
      </div>
    </div>
  )
}
