import type { JSX, ReactNode } from 'react'

/**
 * A value nobody has decided or measured yet, marked so it can't pass for a real one (the
 * system's `.kl-ph`): Lens blue on a soft Lens blue tint, with its text in square brackets. The
 * tint is opaque, so no mesh light behind the page lowers the text's contrast.
 */
export function Placeholder({ children }: { children?: ReactNode }): JSX.Element {
  return (
    <span
      data-placeholder="true"
      className="rounded-[6px] bg-placeholder-tint px-1.5 [overflow-wrap:anywhere] text-lens-blue"
    >
      {children}
    </span>
  )
}
