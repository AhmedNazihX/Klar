import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ExportRequest } from '@/api'
import { Button } from '@/components/Button'
import { ExportFileError, useExportDocument } from '@/hooks/use-document-drafts'

/** Download .docx and Download PDF: the API makes the file from the same result and answers the
 *  draft on screen came from, after its automatic checks. Each click is one request. */
export function DownloadButtons({
  request,
}: {
  request: Omit<ExportRequest, 'format'>
}): JSX.Element {
  const { t } = useTranslation()
  const download = useExportDocument()
  const failure =
    download.error instanceof ExportFileError && download.error.isChecksFailed
      ? t('documents.download.checksFailed')
      : t('documents.download.failed')
  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex flex-wrap gap-2.5">
        <Button
          variant="ghost"
          disabled={download.isPending}
          onClick={() => {
            download.mutate({ ...request, format: 'docx' })
          }}
        >
          {t('documents.download.docx')}
        </Button>
        <Button
          variant="ghost"
          disabled={download.isPending}
          onClick={() => {
            download.mutate({ ...request, format: 'pdf' })
          }}
        >
          {t('documents.download.pdf')}
        </Button>
      </div>
      {download.isError && (
        <p role="alert" className="m-0 text-caption text-risk-prohibited">
          {failure}
        </p>
      )}
    </div>
  )
}
