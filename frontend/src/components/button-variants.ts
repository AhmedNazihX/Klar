import { cva } from 'class-variance-authority'

// Hover lifts 1 px, press settles to 98%, both in duration-press with ease-settle. Buttons never
// shrink in a row: the text beside them wraps instead. Tailwind writes the lift and press as the
// standalone `translate` and `scale` properties, so they are motion-safe only: with reduced motion
// the button keeps still (index.css stops the transitions and the sheen).
/** The Button's classes, also for a link that looks like one (the site nav's action). */
export const buttonVariants = cva(
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
