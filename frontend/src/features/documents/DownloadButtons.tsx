import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ExportRequest } from '@/api'
import { Button } from '@/components/Button'
import {
  documentFailure,
  useExportDocument,
  type DocumentFailure,
} from '@/hooks/use-document-drafts'

const FAILURE_KEYS = {
  'checks-failed': 'documents.download.checksFailed',
  'too-large': 'documents.download.tooLong',
  busy: 'documents.download.busy',
  failed: 'documents.download.failed',
} as const satisfies Record<DocumentFailure, string>

/** Download .docx and Download PDF: the API makes the file from the same result, answers and
 *  size class the draft on screen came from, after its automatic checks. Each click is one
 *  request; nothing is sent again by itself. */
export function DownloadButtons({
  request,
}: {
  request: Omit<ExportRequest, 'format'>
}): JSX.Element {
  const { t } = useTranslation()
  const download = useExportDocument()
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
          {t(FAILURE_KEYS[documentFailure(download.error)])}
        </p>
      )}
    </div>
  )
}
