import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { DraftSection } from '@/api'

import { draftedCount, titleParts } from './interview'

/** A skeleton page's heading (artboard `DocSkeleton`): the document's name, the provision it
 *  follows and the tool it is for, and how many of its sections are drafted. A long German name
 *  breaks inside the word rather than pushing a phone's page sideways. */
export function SkeletonHeader({
  title,
  toolName,
  sections,
}: {
  /** The listed title, "Technical documentation (Annex IV)". */
  title: string
  toolName: string
  sections: readonly DraftSection[]
}): JSX.Element {
  const { t } = useTranslation()
  const { name, source } = titleParts(title)
  const drafted = draftedCount(sections)
  const total = sections.length
  const progress = t('documents.skeleton.progress', { drafted, total })
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="flex min-w-0 flex-col gap-1.5">
        <h1 className="m-0 text-[clamp(28px,6vw,40px)] leading-tight font-semibold tracking-[-0.035em] [overflow-wrap:anywhere] hyphens-auto text-ink">
          {name}
        </h1>
        <p className="m-0 text-body text-slate">
          {source
            ? t('documents.skeleton.intro', { source, tool: toolName })
            : t('documents.skeleton.introNoSource', { tool: toolName })}
        </p>
      </div>
      <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
        <span className="text-label text-slate">{progress}</span>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={drafted}
          aria-label={progress}
          className="h-1.5 w-[220px] max-w-full overflow-hidden rounded-pill bg-ink/10"
        >
          <div
            className="h-full rounded-pill bg-lens-blue"
            style={{ width: `${String(total ? (drafted / total) * 100 : 0)}%` }}
          />
        </div>
      </div>
    </header>
  )
}
