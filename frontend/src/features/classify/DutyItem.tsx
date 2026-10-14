import type { TFunction } from 'i18next'
import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Obligation } from '@/api'
import { ObligationItem } from '@/components/ObligationItem'
import { useLanguage } from '@/hooks/use-language'
import { tickKey } from '@/lib/duty-progress'

import { provisionName } from './provision-names'
import { DUTY_REFERENCE_WIDTH, dutyLabel } from './result-text'

/** The line under a duty, with its relief note after it when it has one. */
function noteWithRelief(t: TFunction, note: ReactNode, relief: string | null): ReactNode {
  if (relief === null) return note
  const line = <span className="basis-full">{t('result.duty.relief', { relief })}</span>
  return note ? (
    <>
      <span>{note}</span>
      {line}
    </>
  ) : (
    line
  )
}

/**
 * One duty with its box, its Art. 111(2) marking and its draft document, as the provider layout
 * (P23) and the Obligations screen (P24) list it; each passes the line under it, the draft's
 * link text and the duty's relief note (`useDutyRelief`), which follows the line. A duty with
 * nothing to tick off gets no box.
 */
export function DutyItem({
  duty,
  relief,
  toolId,
  note,
  docLabel,
  done,
  onTick,
}: {
  duty: Obligation
  /** The duty's relief note for the company, if it gets one. */
  relief: string | null
  toolId: string
  note: ReactNode
  docLabel: ReactNode
  /** The obligation keys ticked off on the tool. */
  done: ReadonlySet<string>
  onTick: (key: string, isDone: boolean) => void
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const key = tickKey(duty)
  const shownNote = noteWithRelief(t, note, relief)
  return (
    <ObligationItem
      label={dutyLabel(duty, language)}
      reference={provisionName(duty.article, language)}
      referenceWidth={DUTY_REFERENCE_WIDTH[language]}
      note={shownNote}
      tag={duty.legacy ? t('result.legacy.tag') : undefined}
      isInformational={key === null}
      docLabel={docLabel}
      documentId={duty.document}
      toolId={toolId}
      checked={key !== null && done.has(key)}
      onCheckedChange={key === null ? undefined : (isDone) => onTick(key, isDone)}
    />
  )
}
