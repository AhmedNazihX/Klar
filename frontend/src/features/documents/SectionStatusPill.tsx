import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { DraftSection } from '@/api'
import { cn } from '@/lib/utils'

/** A skeleton section's status, in words (artboard `DocSkeleton`): beside its heading in the
 *  document and under its name in the section list. */
export function SectionStatusPill({ section }: { section: DraftSection }): JSX.Element {
  const { t } = useTranslation()
  const count = section.unanswered?.length ?? 0
  const label =
    section.status === 'questions'
      ? t('documents.sectionStatus.questions', { count })
      : t(`documents.sectionStatus.${section.status}`)
  return (
    <span
      data-section-status={section.status}
      className={cn(
        'inline-flex min-h-[22px] items-center self-start rounded-pill px-2 text-xs font-semibold whitespace-nowrap',
        section.status === 'drafted' &&
          'bg-risk-minimal-tint text-risk-minimal shadow-[inset_0_0_0_1px_var(--color-risk-minimal-ring)]',
        section.status === 'questions' && 'bg-lens-blue text-white',
        section.status === 'to_fill_in' &&
          'border-[1.5px] border-dashed border-status-info-ring bg-white/60 text-ink-2',
        section.status === 'needs_evidence' &&
          'bg-risk-high-tint text-risk-high shadow-[inset_0_0_0_1px_var(--color-risk-high-ring)]',
        section.status === 'generated_last' &&
          'bg-white/60 text-slate shadow-[inset_0_0_0_1px_var(--color-border-subtle)]',
      )}
    >
      {label}
    </span>
  )
}
