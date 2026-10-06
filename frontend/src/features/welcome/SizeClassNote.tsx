import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { StatusPill } from '@/components/StatusPill'
import { useLawVersion } from '@/hooks/use-law-version'
import type { StaffBand, TurnoverBand } from '@/lib/company-profile'

import { LawQuote } from './LawQuote'
import { describeSize } from './size-note'

/**
 * The derived line under the bands: SME, small mid-cap or neither under the law version on show,
 * what that means for the maximum fines, the provisions it rests on (quoted), and the
 * balance-sheet caveats Klar can't check. Nothing until both bands are chosen.
 */
export function SizeClassNote({
  staffBand,
  turnoverBand,
}: {
  staffBand: StaffBand | null
  turnoverBand: TurnoverBand | null
}): JSX.Element | null {
  const { t } = useTranslation()
  const note = describeSize(staffBand, turnoverBand, useLawVersion())
  if (note === null) return null
  return (
    <div
      data-size-class={note.line}
      className="flex flex-col gap-3 rounded-card-small px-4 py-3.5 glass-thin"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
        <StatusPill status="decided" className="shrink-0 self-start">
          {t(`welcome.size.label.${note.line}`)}
        </StatusPill>
        <p className="m-0 text-body-small text-ink-2">{t(`welcome.size.body.${note.line}`)}</p>
      </div>
      {note.caveats.map((caveat) => (
        <p key={caveat} className="m-0 text-caption text-slate">
          {t(`welcome.size.${caveat}`)}
        </p>
      ))}
      {note.quotes.map((provision) => (
        <LawQuote key={provision} provision={provision} />
      ))}
    </div>
  )
}
