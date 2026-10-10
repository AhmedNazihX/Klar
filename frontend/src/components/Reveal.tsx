import { useRef, type CSSProperties, type JSX, type ReactNode } from 'react'

import { useReveal } from '@/hooks/use-reveal'

export type RevealProps = {
  /** rise: fades in and rises 18 px. focus: also sharpens from a blur, for section headings. */
  variant?: 'rise' | 'focus'
  /** Stagger in ms, in steps of the stagger token (110 ms): the four checks arrive 1, 2, 3, 4. */
  delay?: number
  as?: 'div' | 'section' | 'h2' | 'li'
  id?: string
  className?: string
  children: ReactNode
}

/**
 * Content that arrives as it scrolls into view and leaves in reverse when you scroll back: the
 * public pages' section rhythm (components.md › Reveal). Not for the app's working screens.
 */
export function Reveal({
  variant = 'rise',
  delay = 0,
  as: Tag = 'div',
  id,
  className,
  children,
}: RevealProps): JSX.Element {
  const ref = useRef<HTMLElement>(null)
  useReveal(ref, delay)
  const style = { '--reveal-delay': `${delay}ms` } as CSSProperties
  return (
    <Tag
      ref={(node: HTMLElement | null) => {
        ref.current = node
      }}
      id={id}
      data-reveal={variant}
      className={className}
      style={style}
    >
      {children}
    </Tag>
  )
}
