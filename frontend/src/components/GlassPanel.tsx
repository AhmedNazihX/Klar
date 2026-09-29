import type { ComponentProps, JSX } from 'react'

import { cn } from '@/lib/utils'

export type GlassPanelProps = ComponentProps<'div'> & {
  /** `light` is the frosted white panel; `dark` the ink panel for contrast blocks. */
  tone?: 'light' | 'dark'
}

/** The Brand board's frosted-glass panel. Place it on the `bg-ground` backdrop so the blur shows. */
export function GlassPanel({ tone = 'light', className, ...props }: GlassPanelProps): JSX.Element {
  return (
    <div
      data-tone={tone}
      className={cn(tone === 'dark' ? 'glass-dark' : 'glass', 'rounded-panel', className)}
      {...props}
    />
  )
}
