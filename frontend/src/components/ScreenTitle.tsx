import type { JSX, ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** A screen's page heading (its one h1): 30 px on a phone, the page heading size from md up. */
export function ScreenTitle({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}): JSX.Element {
  return (
    <h1
      className={cn(
        'm-0 text-[30px] leading-tight font-semibold tracking-[-0.03em] text-ink md:text-heading-page',
        className,
      )}
    >
      {children}
    </h1>
  )
}
