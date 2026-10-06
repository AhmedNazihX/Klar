import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { classifyWriteFailure, type WriteKind } from '@/lib/company-profile'

/**
 * Why a save or an import failed. A full storage (PT507, decision 027) says how to make room, apart
 * from every other error. The server's own text is never shown: it may carry details.
 */
export function WriteFailureMessage({
  error,
  kind,
}: {
  error: unknown
  kind: WriteKind
}): JSX.Element {
  const { t } = useTranslation()
  const failure = classifyWriteFailure(error, kind)
  return (
    <div
      role="alert"
      data-failure={failure}
      className="flex flex-col gap-1 rounded-card-small px-4 py-3 text-body-small text-ink glass-thin"
    >
      {failure === 'storage-full' ? (
        <>
          <p className="m-0 font-semibold text-risk-prohibited">
            {t('welcome.failure.storageFull')}
          </p>
          <p className="m-0">
            {t('welcome.failure.storageFullHint')}{' '}
            <Link to="/app/your-data" className="font-medium text-lens-blue hover:underline">
              {t('welcome.failure.storageFullLink')}
            </Link>
          </p>
        </>
      ) : (
        <p className="m-0">
          {failure === 'too-large' && t('welcome.failure.tooLarge')}
          {failure === 'bad-file' && t('welcome.failure.badFile')}
          {failure === 'failed' && t('welcome.failure.failed')}
        </p>
      )}
    </div>
  )
}
