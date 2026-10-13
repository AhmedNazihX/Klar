import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, Obligation } from '@/api'
import { ObligationItem } from '@/components/ObligationItem'
import { useLanguage } from '@/hooks/use-language'
import { useLawVersion } from '@/hooks/use-law-version'
import { useReliefNotes } from '@/hooks/use-relief-notes'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'
import { tickKey } from '@/lib/duty-progress'

import { provisionName } from './provision-names'
import { isRelieved, reliefNote } from './relief'
import { DUTY_REFERENCE_WIDTH, dutyLabel } from './result-text'

/** The line under a duty, with its relief note after it when the company gets one: the
 *  obligations table's for the duty's key, looked up for `result`'s roles and class. */
function useNoteWithRelief(
  duty: Obligation,
  result: ClassificationResult,
  note: ReactNode,
): ReactNode {
  const { t } = useTranslation()
  const language = useLanguage()
  const shown = useLawVersion()
  const sizeClass = useUserDataOverview().data?.profile?.sizeClass
  const table = useReliefNotes(result, isRelieved(sizeClass, shown))
  const relief = duty.key && table ? reliefNote(table[duty.key], language) : null
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
 * (P23) and the Obligations screen (P24) list it; each passes the line under it and the draft's
 * link text, and the relief note follows it for an SME or a small mid-cap (`isRelieved`). A
 * duty with nothing to tick off gets no box.
 */
export function DutyItem({
  duty,
  result,
  toolId,
  note,
  docLabel,
  done,
  onTick,
}: {
  duty: Obligation
  /** The result that lists the duty. */
  result: ClassificationResult
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
  const shownNote = useNoteWithRelief(duty, result, note)
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
