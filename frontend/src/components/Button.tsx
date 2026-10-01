import type { VariantProps } from 'class-variance-authority'
import type { ComponentProps, JSX } from 'react'

import { cn } from '@/lib/utils'

import { buttonVariants } from './button-variants'
import { Icon } from './Icon'
import type { IconName } from './icon-files'

type ButtonVariants = VariantProps<typeof buttonVariants>

export type ButtonProps = ComponentProps<'button'> &
  ButtonVariants & {
    /** Leading icon from the Klar set (rare: "Add a tool" is the usual exception). */
    icon?: IconName
  }

const ICON_SIZE = { sm: 14, md: 16, lg: 16 } as const

/** The action button. The label is a verb and its object, in sentence case, with no arrows. */
export function Button({
  variant,
  size,
  icon,
  className,
  children,
  type = 'button',
  ...props
}: ButtonProps): JSX.Element {
  return (
    <button
      type={type}
      data-slot="klar-button"
      data-variant={variant ?? 'primary'}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {icon && <Icon name={icon} size={ICON_SIZE[size ?? 'md']} />}
      {children}
    </button>
  )
}
