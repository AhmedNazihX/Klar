import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { StatusPill } from '@/components/StatusPill'
import {
  deriveSizeClass,
  hasSmeStaffBand,
  type StaffBand,
  type TurnoverBand,
} from '@/lib/company-profile'

import { LawQuote } from './LawQuote'

/**
 * The derived line under the bands: SME, small mid-cap or neither, what that means for the fines
 * (Art. 99(6) against Art. 99(3), both quoted). Nothing until both bands are chosen. A small
 * mid-cap with under 250 staff may still be an SME on the balance-sheet test, which Klar can't apply.
 */
export function SizeClassNote({
  staffBand,
  turnoverBand,
}: {
  staffBand: StaffBand | null
  turnoverBand: TurnoverBand | null
}): JSX.Element | null {
  const { t } = useTranslation()
  const sizeClass = deriveSizeClass(staffBand, turnoverBand)
  if (sizeClass === null) return null
  return (
    <div
      data-size-class={sizeClass}
      className="flex flex-col gap-3 rounded-card-small px-4 py-3.5 glass-thin"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
        <StatusPill status="decided" className="shrink-0 self-start">
          {t(`welcome.size.label.${sizeClass}`)}
        </StatusPill>
        <p className="m-0 text-body-small text-ink-2">{t(`welcome.size.body.${sizeClass}`)}</p>
      </div>
      {sizeClass === 'smc' && hasSmeStaffBand(staffBand) && (
        <p className="m-0 text-caption text-slate">{t('welcome.size.maybeSme')}</p>
      )}
      <LawQuote provision="art99_3" />
      <LawQuote provision="art99_6" />
    </div>
  )
}
