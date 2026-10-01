import type { JSX, ReactNode } from 'react'

import { cn } from '@/lib/utils'

/**
 * The root of a public page: the mist ground with its four mesh lights, behind the glass. One per
 * page. The two drifting lights and the cursor light (components.md › MistGround) come with the
 * landing page (P16); this is the still ground they move over.
 */
export function MistGround({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}): JSX.Element {
  return (
    <div data-ground="mist" className={cn('relative isolate min-h-dvh bg-ground', className)}>
      {children}
    </div>
  )
}
