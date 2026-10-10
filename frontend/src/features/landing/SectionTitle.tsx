import type { JSX, ReactNode } from 'react'

import { Reveal } from '@/components/Reveal'
import { cn } from '@/lib/utils'

// The artboards' three heading sizes: display-section (52 px), the medium 44 px of the accuracy,
// agents and closing panels, and heading-page (40 px) in the timeline panel. Smaller on a phone.
const SIZE_CLASS = {
  section: 'text-[36px] leading-[1.08] tracking-[-0.035em] md:text-display-section',
  medium: 'text-[32px] leading-[1.08] tracking-[-0.035em] md:text-[44px] md:tracking-[-0.04em]',
  page: 'text-[30px] leading-[1.1] tracking-[-0.03em] md:text-heading-page',
} as const

/** A landing section's heading (components.md › SectionHeader): a claim that comes into focus. */
export function SectionTitle({
  id,
  size = 'section',
  className,
  children,
}: {
  id?: string
  size?: keyof typeof SIZE_CLASS
  className?: string
  children: ReactNode
}): JSX.Element {
  return (
    <Reveal
      as="h2"
      variant="focus"
      id={id}
      className={cn('m-0 font-semibold text-balance', SIZE_CLASS[size], className)}
    >
      {children}
    </Reveal>
  )
}
