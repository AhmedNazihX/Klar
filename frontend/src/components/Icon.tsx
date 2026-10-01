import type { CSSProperties, JSX } from 'react'

import { cn } from '@/lib/utils'

import { ICON_FILES, type IconName } from './icon-files'

const DEFAULT_SIZE = 18

export type IconProps = {
  name: IconName
  /** px, default 18. */
  size?: number
  /** Give a title only when the icon stands alone and carries meaning; otherwise it is hidden. */
  title?: string
  className?: string
}

/**
 * One of the Klar line icons, painted in currentColor: the copied file is the mask, so the drawing
 * stays exactly the system's. Icons label; they never decorate and never replace a word.
 */
export function Icon({ name, size = DEFAULT_SIZE, title, className }: IconProps): JSX.Element {
  const mask = `url("${ICON_FILES[name]}") center / contain no-repeat`
  const style: CSSProperties = { width: size, height: size, mask, WebkitMask: mask }
  return (
    <span
      data-icon={name}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      className={cn('inline-block shrink-0 bg-current', className)}
      style={style}
    />
  )
}
