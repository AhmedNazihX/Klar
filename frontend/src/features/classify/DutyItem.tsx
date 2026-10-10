import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Obligation } from '@/api'
import { ObligationItem } from '@/components/ObligationItem'
import { useLanguage } from '@/hooks/use-language'
import { tickKey } from '@/lib/duty-progress'

import { provisionName } from './provision-names'
import { DUTY_REFERENCE_WIDTH, dutyLabel } from './result-text'

/**
 * One duty with its box, its Art. 111(2) marking and its draft document, as the provider layout
 * (P23) and the Obligations screen (P24) list it; each passes the line under it and the draft's
 * link text. A duty with nothing to tick off gets no box.
 */
export function DutyItem({
  duty,
  toolId,
  note,
  docLabel,
  done,
  onTick,
}: {
  duty: Obligation
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
  return (
    <ObligationItem
      label={dutyLabel(duty, language)}
      reference={provisionName(duty.article, language)}
      referenceWidth={DUTY_REFERENCE_WIDTH[language]}
      note={note}
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
