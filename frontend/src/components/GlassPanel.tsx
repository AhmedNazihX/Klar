import type { HTMLAttributes, JSX, PointerEvent } from 'react'

import { cn } from '@/lib/utils'

const TONE_CLASS = { glass: 'glass', thin: 'glass-thin', dark: 'glass-dark' } as const

const RADIUS_CLASS = {
  small: 'rounded-card-small',
  tile: 'rounded-tile',
  card: 'rounded-card',
  panel: 'rounded-panel',
  feature: 'rounded-feature',
} as const

export type GlassPanelProps = HTMLAttributes<HTMLElement> & {
  /** glass: cards and panels. thin: chips and cards inside a panel. dark: code and dark tiles only. */
  tone?: keyof typeof TONE_CLASS
  /** card (28 px) by default; panel (32 px) for the sidebar and the result card; feature (36 px). */
  radius?: keyof typeof RADIUS_CLASS
  /** Default true: 28 px padding (space-7). */
  padded?: boolean
  /** A soft light follows the cursor across the glass. Never on chat or long-reading panels. */
  glint?: boolean
  /** Lifts 3 px on hover with a deeper shadow, for cards that open something. */
  lift?: boolean
  as?: 'div' | 'section' | 'article' | 'aside' | 'li'
}

// The glint's position, in the panel's own pixels.
function followPointer(event: PointerEvent<HTMLElement>): void {
  const panel = event.currentTarget
  const rect = panel.getBoundingClientRect()
  panel.style.setProperty('--mx', `${event.clientX - rect.left}px`)
  panel.style.setProperty('--my', `${event.clientY - rect.top}px`)
}

/** Frosted glass over the mist ground: the surface everything sits on. */
export function GlassPanel({
  tone = 'glass',
  radius = 'card',
  padded = true,
  glint = false,
  lift = false,
  as: Tag = 'div',
  className,
  onPointerMove,
  ...props
}: GlassPanelProps): JSX.Element {
  return (
    <Tag
      data-tone={tone}
      className={cn(
        TONE_CLASS[tone],
        RADIUS_CLASS[radius],
        padded && 'p-7',
        glint && 'glint',
        lift && 'lift',
        className,
      )}
      onPointerMove={(event) => {
        if (glint) followPointer(event)
        onPointerMove?.(event)
      }}
      {...props}
    />
  )
}
