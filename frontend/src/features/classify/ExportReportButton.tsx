import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { reportFailureKey, useExportResultReport } from '@/hooks/use-report-export'
import { useLanguage } from '@/hooks/use-language'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'

import type { ClassificationRun } from './classification-store'

/**
 * Export PDF: the report for a lawyer (artboard `ExportPDF`), made by the API from this run's
 * result in the screen's language, with the tool's name and the company's from its profile. On
 * Result and Reviewer; the ambiguous result's "Take it to a lawyer" (P22) uses it too.
 */
export function ExportReportButton({ run }: { run: ClassificationRun }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const overview = useUserDataOverview()
  const exportReport = useExportResultReport(run.toolId)
  return (
    // The message hangs below the button, out of the flow, so the header's actions never move.
    <div className="relative flex">
      <Button
        variant="ghost"
        disabled={exportReport.isPending}
        onClick={() => {
          exportReport.mutate({
            result: run.result,
            language,
            format: 'pdf',
            tool_name: run.name,
            company: overview.data?.profile?.companyName ?? null,
          })
        }}
      >
        {exportReport.isPending ? t('report.pending') : t('report.export')}
      </Button>
      {exportReport.isError && (
        <p
          role="alert"
          className="absolute top-full right-0 z-10 m-0 mt-1.5 w-max max-w-[min(20rem,calc(100vw-2rem))] text-right text-caption text-risk-prohibited"
        >
          {t(reportFailureKey(exportReport.error))}
        </p>
      )}
    </div>
  )
}
