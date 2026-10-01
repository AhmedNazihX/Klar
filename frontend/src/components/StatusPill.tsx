import { cva } from 'class-variance-authority'
import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import type { Status } from './pill-kinds'

// Wraps inside the pill rather than overflowing: German labels run about 30% longer.
const statusVariants = cva(
  'inline-flex max-w-full items-center rounded-pill leading-tight font-semibold',
  {
    variants: {
      status: {
        decided: 'bg-white/70 text-ink-2 shadow-[inset_0_0_0_1px_var(--color-border-subtle)]',
        // Uncertain statuses never look like a decided class.
        ambiguous:
          'bg-status-ambiguous-tint text-status-ambiguous shadow-[inset_0_0_0_1px_var(--color-status-ambiguous-ring)]',
        // Dashed: something is still to be filled in.
        'needs-info':
          'border-[1.5px] border-dashed border-status-info-ring bg-status-info-fill text-status-info',
        // The stamp on every drafted document.
        draft:
          'rounded-[6px] bg-transparent font-bold tracking-[0.08em] text-risk-high shadow-[inset_0_0_0_1.5px_rgb(135_58_0/0.45)]',
      },
      size: {
        sm: 'min-h-[22px] px-2 py-0.5 text-xs',
        md: 'min-h-[26px] px-2.5 py-1 text-[13px]',
      },
    },
    compoundVariants: [{ status: 'draft', className: 'min-h-6 text-xs' }],
  },
)

export type StatusPillProps = {
  status: Status
  size?: 'sm' | 'md'
  /** Label override; defaults to the translated status name. */
  children?: ReactNode
  className?: string
}

/** How settled a result is. It sits next to a RiskPill and never replaces one. */
export function StatusPill({
  status,
  size = 'md',
  children,
  className,
}: StatusPillProps): JSX.Element {
  const { t } = useTranslation()
  return (
    <span data-status={status} className={cn(statusVariants({ status, size }), className)}>
      {children ?? t(`status.${status}`)}
    </span>
  )
}
