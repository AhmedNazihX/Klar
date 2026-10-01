import type { JSX, ReactNode } from 'react'

export type LawDateProps = {
  /** Under the amended text (the default view). */
  amended: ReactNode
  /** Under the original 2024 text. */
  original: ReactNode
  className?: string
}

/**
 * A date the Digital Omnibus moved: the amended date, or the original one while a LawSwitch in the
 * same scope shows the 2024 text. Only for dates that differ; write the others as plain text.
 */
export function LawDate({ amended, original, className }: LawDateProps): JSX.Element {
  return (
    <span className={className}>
      <span className="law-amended-only">{amended}</span>
      <span className="law-original-only">{original}</span>
    </span>
  )
}
