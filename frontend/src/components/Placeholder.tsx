import type { JSX, ReactNode } from 'react'

/**
 * A value nobody has decided or measured yet, marked so it can't pass for a real one (the
 * system's `.kl-ph`): Lens blue on a soft Lens blue tint, with its text in square brackets.
 */
export function Placeholder({ children }: { children?: ReactNode }): JSX.Element {
  return (
    <span
      data-placeholder="true"
      className="rounded-[6px] bg-lens-blue/8 px-1.5 [overflow-wrap:anywhere] text-lens-blue"
    >
      {children}
    </span>
  )
}
