import { cva } from 'class-variance-authority'
import type { ComponentProps, JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import type { PillKind } from './pill-kinds'

// One line at 26 px as on the board. A label longer than its container (German runs about 30%
// longer, e.g. "Außerhalb des Anwendungsbereichs") wraps inside the pill instead of overflowing.
const pillVariants = cva(
  'inline-flex min-h-[26px] max-w-full items-center gap-1.5 rounded-[13px] px-2.5 py-1 text-[13px] leading-tight font-semibold',
  {
    variants: {
      kind: {
        prohibited:
          'bg-risk-prohibited-tint text-risk-prohibited shadow-[inset_0_0_0_1px_var(--color-risk-prohibited-ring)]',
        high_risk:
          'bg-risk-high-tint text-risk-high shadow-[inset_0_0_0_1px_var(--color-risk-high-ring)]',
        limited_risk:
          'bg-risk-limited-tint text-risk-limited shadow-[inset_0_0_0_1px_var(--color-risk-limited-ring)]',
        minimal_risk:
          'bg-risk-minimal-tint text-risk-minimal shadow-[inset_0_0_0_1px_var(--color-risk-minimal-ring)]',
        out_of_scope:
          'bg-risk-out-tint text-risk-out shadow-[inset_0_0_0_1px_var(--color-risk-out-ring)]',
        // The uncertain statuses never look like a decided class: no dot, their own outline.
        legally_ambiguous:
          'bg-status-ambiguous-tint text-status-ambiguous shadow-[inset_0_0_0_1px_var(--color-status-ambiguous-ring)]',
        needs_more_information:
          'border-[1.5px] border-dashed border-status-info-ring bg-status-info-fill text-status-info',
      },
    },
  },
)

// Only the decided classes carry a colour dot.
const DOT_CLASS: Record<PillKind, string | null> = {
  prohibited: 'bg-risk-prohibited-dot',
  high_risk: 'bg-risk-high-dot',
  limited_risk: 'bg-risk-limited-dot',
  minimal_risk: 'bg-risk-minimal-dot',
  out_of_scope: 'bg-risk-out-dot',
  legally_ambiguous: null,
  needs_more_information: null,
}

export type RiskPillProps = Omit<ComponentProps<'span'>, 'children'> & {
  kind: PillKind
  /** Label override that keeps the class's word, e.g. "High-risk, assumed" (InventoryTable). */
  label?: string
}

/** A risk class or status as a pill. It always shows the word; colour only supports it. */
export function RiskPill({ kind, label, className, ...props }: RiskPillProps): JSX.Element {
  const { t } = useTranslation()
  const dot = DOT_CLASS[kind]
  return (
    <span data-kind={kind} className={cn(pillVariants({ kind }), className)} {...props}>
      {dot && <span aria-hidden="true" className={cn('size-2 shrink-0 rounded-full', dot)} />}
      {label ?? t(`pill.${kind}`)}
    </span>
  )
}
