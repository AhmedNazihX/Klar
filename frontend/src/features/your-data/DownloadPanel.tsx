import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { ImportDataButton } from '@/features/welcome/ImportDataButton'
import { useExportUserData } from '@/hooks/use-export-user-data'
import { supabase } from '@/lib/supabase'

/**
 * "Download everything": the data file (export_my_data as JSON), and Import, which restores such
 * a file (decision 026 item 8). P25 adds the PDF report here.
 */
export function DownloadPanel(): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const exportData = useExportUserData()
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-3.5 p-6.5">
      <h2 id={headingId} className="m-0 text-heading-panel text-ink">
        {t('yourData.download.heading')}
      </h2>
      <p className="m-0 text-label font-normal text-slate">{t('yourData.download.body')}</p>
      <div>
        <Button
          disabled={exportData.isPending || supabase === null}
          onClick={() => exportData.mutate()}
        >
          {exportData.isPending ? t('yourData.download.pending') : t('yourData.download.button')}
        </Button>
      </div>
      {exportData.isError && (
        <p role="alert" className="m-0 text-body-small text-risk-prohibited">
          {t('yourData.download.failed')}
        </p>
      )}
      <ImportDataButton className="items-start border-t border-hairline pt-3.5" />
    </GlassPanel>
  )
}
