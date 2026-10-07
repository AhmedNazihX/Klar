import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import { useMyDataCounts } from '@/hooks/use-my-data-counts'
import { formatBytes, type MyDataCounts } from '@/lib/user-data'

// The rows "What Klar keeps" lists, in order: only what is stored (Q&A isn't, decision 026 item 6;
// drafts aren't either, so the artboard's "Draft documents" row is left out).
const ROWS = [
  'systems',
  'classifications',
  'interviewAnswers',
  'dutyProgress',
  'companyProfiles',
] as const satisfies readonly (keyof MyDataCounts)[]

/** "What Klar keeps": a count per kind of stored data (my_data_counts), the storage used against
 *  the budget (decision 027), and the 30-day deletion (decision 013). */
export function KeptDataPanel(): JSX.Element {
  const { t, i18n } = useTranslation()
  const headingId = useId()
  const counts = useMyDataCounts()
  const data = counts.data
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-1.5 p-6.5">
      <h2 id={headingId} className="m-0 mb-2 text-heading-panel text-ink">
        {t('yourData.keep.heading')}
      </h2>
      <dl className="m-0 flex flex-col" aria-busy={counts.isPending}>
        {ROWS.map((field) => (
          <div
            key={field}
            className="flex min-h-10 items-center justify-between gap-3 border-t border-hairline text-body-small"
          >
            <dt className="text-ink">{t(`yourData.keep.${field}`)}</dt>
            <dd className="m-0 font-semibold text-ink">{data ? data[field] : '–'}</dd>
          </div>
        ))}
      </dl>
      {data && (
        <p className="m-0 border-t border-hairline pt-2.5 text-caption text-slate">
          {t('yourData.keep.storage', {
            used: formatBytes(data.storageBytes, i18n.language),
            budget: formatBytes(data.storageBudgetBytes, i18n.language),
          })}
        </p>
      )}
      {counts.isError && (
        <p role="alert" className="m-0 text-body-small text-risk-prohibited">
          {t('yourData.keep.failed')}
        </p>
      )}
      <p className="m-0 mt-2.5 text-caption font-normal text-slate">
        {t('yourData.keep.retention')}
      </p>
    </GlassPanel>
  )
}
