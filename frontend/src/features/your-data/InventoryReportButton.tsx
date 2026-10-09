import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { useInventoryTools } from '@/hooks/use-inventory-tools'
import { useLanguage } from '@/hooks/use-language'
import { reportFailureKey, reportTool, useExportInventoryReport } from '@/hooks/use-report-export'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'

/**
 * Report (PDF): the inventory, results and duties for people to read (artboard `YourData`; the
 * data file is for other tools). The API makes it from each tool's latest stored result, in the
 * screen's language; it waits for the tools to load.
 */
export function InventoryReportButton(): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const tools = useInventoryTools()
  const overview = useUserDataOverview()
  const exportReport = useExportInventoryReport()
  return (
    <>
      <Button
        variant="ghost"
        disabled={exportReport.isPending || !tools.data}
        onClick={() => {
          if (!tools.data) return
          exportReport.mutate({
            tools: tools.data.map((tool) => reportTool(tool, language)),
            language,
            format: 'pdf',
            company: overview.data?.profile?.companyName ?? null,
          })
        }}
      >
        {exportReport.isPending ? t('report.pending') : t('yourData.download.report')}
      </Button>
      {exportReport.isError && (
        <p role="alert" className="m-0 basis-full text-body-small text-risk-prohibited">
          {t(reportFailureKey(exportReport.error))}
        </p>
      )}
    </>
  )
}
