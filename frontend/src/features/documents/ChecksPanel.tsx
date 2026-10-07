import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { CheckResult } from '@/api'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import { cn } from '@/lib/utils'

/** The three automatic checks, as the Documents artboard names them; a skeleton's panel reads
 *  "Before you sign" (artboard `DocSkeleton`). Each check says in words whether it passed. */
export function ChecksPanel({
  checks,
  isSkeleton,
}: {
  checks: readonly CheckResult[]
  isSkeleton: boolean
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-3 p-5.5">
      <h2 id={headingId} className="m-0 text-[17px] font-semibold text-ink">
        {t(isSkeleton ? 'documents.checks.skeletonTitle' : 'documents.checks.title')}
      </h2>
      {isSkeleton && (
        <p className="m-0 text-caption text-slate">{t('documents.checks.skeletonIntro')}</p>
      )}
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {checks.map((check) => (
          <li
            key={check.check}
            data-passed={check.passed}
            className="flex items-center gap-2.5 text-label text-ink"
          >
            <span
              className={cn(
                'flex size-5 shrink-0 items-center justify-center rounded-full',
                check.passed
                  ? 'bg-risk-minimal-tint text-risk-minimal'
                  : 'bg-risk-prohibited-tint text-risk-prohibited',
              )}
            >
              <Icon name={check.passed ? 'check' : 'alert'} size={11} />
            </span>
            <span className="grow">{t(`documents.checks.${check.check}`)}</span>
            <span className="sr-only">
              {t(check.passed ? 'documents.checks.passed' : 'documents.checks.failed')}
            </span>
          </li>
        ))}
      </ul>
    </GlassPanel>
  )
}
