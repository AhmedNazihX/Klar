import { useId, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { ImportDataButton } from '@/features/welcome/ImportDataButton'
import { useExportUserData } from '@/hooks/use-export-user-data'
import { useInventoryTools } from '@/hooks/use-inventory-tools'
import { useLanguage } from '@/hooks/use-language'
import { reportFailureKey, reportTool, useExportInventoryReport } from '@/hooks/use-report-export'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'
import { supabase } from '@/lib/supabase'

type DownloadChoice = 'report' | 'data'

const CHOICES = [
  { value: 'report', label: 'yourData.download.reportChoice' },
  { value: 'data', label: 'yourData.download.dataChoice' },
] as const satisfies readonly { value: DownloadChoice; label: string }[]

/**
 * "Download everything" (artboard `YourData`): one choice, the report (PDF) of the inventory,
 * results and duties for people (P25, the default) or the data file (export_my_data as JSON)
 * for other tools, and one Download button; then Import, which restores a data file (decision
 * 026 item 8). The report is made by the API from each tool's latest stored result, in the
 * screen's language, once the tools have loaded.
 */
export function DownloadPanel(): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const language = useLanguage()
  const [choice, setChoice] = useState<DownloadChoice>('report')
  const exportData = useExportUserData()
  const exportReport = useExportInventoryReport()
  const tools = useInventoryTools()
  const overview = useUserDataOverview()
  const isPending = exportData.isPending || exportReport.isPending
  const isReady = choice === 'report' ? tools.data !== undefined : supabase !== null

  function download(): void {
    exportData.reset()
    exportReport.reset()
    if (choice === 'data') {
      exportData.mutate()
      return
    }
    if (!tools.data) return
    exportReport.mutate({
      tools: tools.data.map((tool) => reportTool(tool, language)),
      language,
      format: 'pdf',
      company: overview.data?.profile?.companyName ?? null,
      size_class: overview.data?.profile?.sizeClass ?? null,
    })
  }

  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-3.5 p-6.5">
      <h2 id={headingId} className="m-0 text-heading-panel text-ink">
        {t('yourData.download.heading')}
      </h2>
      <p className="m-0 text-label font-normal text-slate">{t('yourData.download.body')}</p>
      <div role="radiogroup" aria-labelledby={headingId} className="flex flex-col gap-2">
        {CHOICES.map(({ value, label }) => (
          <label
            key={value}
            className="flex cursor-pointer items-center gap-3 rounded-item px-3.5 py-3 text-body-small text-ink glass-thin"
          >
            <input
              type="radio"
              name={`${headingId}-choice`}
              value={value}
              checked={choice === value}
              onChange={() => setChoice(value)}
              className="m-0 size-4 accent-lens-blue"
            />
            {t(label)}
          </label>
        ))}
      </div>
      <div>
        <Button disabled={isPending || !isReady} onClick={download}>
          {isPending ? t('yourData.download.pending') : t('yourData.download.button')}
        </Button>
      </div>
      {exportData.isError && (
        <p role="alert" className="m-0 text-body-small text-risk-prohibited">
          {t('yourData.download.failed')}
        </p>
      )}
      {exportReport.isError && (
        <p role="alert" className="m-0 text-body-small text-risk-prohibited">
          {t(reportFailureKey(exportReport.error))}
        </p>
      )}
      <ImportDataButton className="items-start border-t border-hairline pt-3.5" />
    </GlassPanel>
  )
}
