import { useId, type JSX, type ReactNode } from 'react'

import { Button } from './Button'

export type ChangeBannerProps = {
  title: ReactNode
  /** Why it changed, in one or two sentences. */
  children?: ReactNode
  /** Usually two RiskPills. */
  before: ReactNode
  after: ReactNode
  /** Read out between the two pills in place of the arrow, e.g. "changed to". */
  changeLabel: string
  runLabel?: ReactNode
  onUndo?: () => void
  undoLabel?: string
  isUndoing?: boolean
}

/** What a re-run changed, at the top of the result: the class before and after, why, the run
 *  number and an undo. The Lens blue edge marks it as Klar's update, not a warning. */
export function ChangeBanner({
  title,
  children,
  before,
  after,
  changeLabel,
  runLabel,
  onUndo,
  undoLabel,
  isUndoing = false,
}: ChangeBannerProps): JSX.Element {
  const headingId = useId()
  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-3 rounded-card border-l-4 border-lens-blue px-6 py-5 glass"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={headingId} className="m-0 text-heading-small text-ink">
          {title}
        </h2>
        {runLabel && <span className="text-caption font-normal text-slate">{runLabel}</span>}
      </div>
      {children}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex flex-wrap items-center gap-2">
          {before}
          <span aria-hidden="true" className="text-slate">
            →
          </span>
          <span className="sr-only">{changeLabel}</span>
          {after}
        </span>
        {onUndo && undoLabel && (
          <Button variant="ghost" size="sm" onClick={onUndo} disabled={isUndoing}>
            {undoLabel}
          </Button>
        )}
      </div>
    </section>
  )
}
