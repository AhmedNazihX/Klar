import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { DraftSection } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { cn } from '@/lib/utils'

import { sectionAnchor } from './interview'
import { SectionStatusPill } from './SectionStatusPill'

/** A skeleton's sections, numbered, each with its status, linking to the section in the
 *  document (artboard `DocSkeleton`'s left column). */
export function SectionList({
  source,
  sections,
  className,
}: {
  /** The provision the skeleton follows ("Annex IV"); null names the list plainly. */
  source: string | null
  sections: readonly DraftSection[]
  className?: string
}): JSX.Element {
  const { t } = useTranslation()
  const label = source
    ? t('documents.skeleton.sections', { source })
    : t('documents.skeleton.sectionsPlain')
  return (
    <GlassPanel
      as="div"
      padded={false}
      className={cn('flex shrink-0 flex-col gap-0.5 px-3 py-4', className)}
    >
      <nav aria-label={label}>
        <p className="m-0 px-3 pt-1 pb-2 text-label font-medium text-slate">{label}</p>
        <ol className="m-0 flex list-none flex-col gap-0.5 p-0">
          {sections.map((section, index) => (
            <li key={section.key}>
              <a
                href={`#${sectionAnchor(section.key)}`}
                className="flex items-start gap-2.5 rounded-item px-3 py-2.5 text-ink no-underline hover:bg-white/45"
              >
                <span className="w-5 shrink-0 pt-px text-label font-semibold text-lens-blue">
                  {index + 1}
                </span>
                <span className="flex min-w-0 flex-col gap-1.5">
                  <span className="text-body-small leading-snug font-medium">
                    {section.heading}
                  </span>
                  <SectionStatusPill section={section} />
                </span>
              </a>
            </li>
          ))}
        </ol>
      </nav>
    </GlassPanel>
  )
}
