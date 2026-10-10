import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { Button } from './Button'
import { EvidenceTag } from './EvidenceTag'
import type { Evidence } from './pill-kinds'

export type FactCardProps = {
  fact: ReactNode
  evidence: Evidence
  /** Assumed facts offer Change and Confirm; the consumer handles them (confirming reruns the
   *  checks with the fact stated, P5b). */
  onChange?: () => void
  onConfirm?: () => void
  /** While a re-run is on its way, Confirm can't start another. */
  isBusy?: boolean
}

/** One fact a result rests on, with its evidence tag. Assumed cards get a Lens blue ring so they
 *  are found first, and Change and Confirm. */
export function FactCard({
  fact,
  evidence,
  onChange,
  onConfirm,
  isBusy = false,
}: FactCardProps): JSX.Element {
  const { t } = useTranslation()
  const isAssumed = evidence === 'assumed'
  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-card-small px-3.5 py-3 glass-thin',
        isAssumed && 'shadow-[inset_0_1px_0_rgb(255_255_255/0.85),0_0_0_1.5px_rgb(45_75_224/0.28)]',
      )}
    >
      <span className="text-body-small font-medium text-ink">{fact}</span>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <EvidenceTag kind={evidence} />
        {isAssumed && (onChange || onConfirm) && (
          <span className="flex shrink-0 gap-2">
            {onChange && (
              <Button variant="ghost" size="sm" onClick={onChange}>
                {t('result.facts.change')}
              </Button>
            )}
            {onConfirm && (
              <Button variant="ghost" size="sm" onClick={onConfirm} disabled={isBusy}>
                {t('result.facts.confirm')}
              </Button>
            )}
          </span>
        )}
      </div>
    </div>
  )
}
