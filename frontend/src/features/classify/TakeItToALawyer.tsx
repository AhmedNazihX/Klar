import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'

import type { ClassificationRun } from './classification-store'
import { ExportReportButton } from './ExportReportButton'

/** "Take it to a lawyer" on a legally ambiguous result (artboard `ResultAmbiguous`): the
 *  reviewer view holds both readings, the facts and every quoted provision; Export PDF makes the
 *  report for a lawyer (P25). */
export function TakeItToALawyer({
  run,
  onOpenReviewer,
}: {
  run: ClassificationRun
  onOpenReviewer: () => void
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-3 p-6 xl:w-[380px] xl:shrink-0"
    >
      <h2 id={headingId} className="m-0 text-heading-panel text-ink">
        {t('ambiguous.lawyer.heading')}
      </h2>
      <p className="m-0 text-body-small text-slate">{t('ambiguous.lawyer.body')}</p>
      <div className="mt-auto flex flex-wrap gap-2.5">
        <Button onClick={onOpenReviewer}>{t('ambiguous.lawyer.openReviewer')}</Button>
        <ExportReportButton run={run} />
      </div>
    </GlassPanel>
  )
}
