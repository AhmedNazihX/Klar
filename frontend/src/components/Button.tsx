import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps, JSX } from 'react'

import { cn } from '@/lib/utils'

import { Icon } from './Icon'
import type { IconName } from './icon-files'

// Hover lifts 1 px, press settles to 98%, both in duration-press with ease-settle. Buttons never
// shrink in a row: the text beside them wraps instead. Tailwind writes the lift and press as the
// standalone `translate` and `scale` properties, so they are motion-safe only: with reduced motion
// the button keeps still (index.css stops the transitions and the sheen).
const buttonVariants = cva(
  'relative inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 overflow-hidden rounded-pill whitespace-nowrap no-underline transition-[translate,scale,box-shadow,filter] duration-(--duration-press) ease-settle disabled:pointer-events-none disabled:opacity-50 motion-safe:hover:-translate-y-px motion-safe:active:translate-y-0 motion-safe:active:scale-[0.98]',
  {
    variants: {
      variant: {
        // The liquid Lens blue: one per view, for the step the screen exists for.
        primary:
          'liquid-primary border border-white/35 font-semibold text-white shadow-button hover:shadow-button-hover hover:brightness-106',
        // Glass, for everything else.
        ghost:
          'border border-white/70 bg-white/45 font-medium text-ink shadow-button-ghost backdrop-blur-thin hover:bg-white/62',
      },
      size: {
        sm: 'h-[34px] px-3.5 text-[13px] leading-none',
        md: 'h-11 px-5 text-[15px] leading-none',
        lg: 'h-13 px-6.5 text-base leading-none',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

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
