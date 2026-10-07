import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { Button } from './Button'
import { EvidenceTag } from './EvidenceTag'
import type { Evidence } from './pill-kinds'

export type FactCardProps = {
  fact: ReactNode
  evidence: Evidence
  /** Assumed facts offer Change and Confirm; the consumer handles both. */
  onConfirm?: () => void
  onChange?: () => void
}

/** One fact a result rests on, with its evidence tag. Assumed cards get a Lens blue ring so they
 *  are found first, and Change and Confirm. */
export function FactCard({ fact, evidence, onConfirm, onChange }: FactCardProps): JSX.Element {
  const { t } = useTranslation()
  const isAssumed = evidence === 'assumed'
  const hasActions = isAssumed && (onConfirm ?? onChange)
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
        {hasActions && (
          <div className="flex shrink-0 gap-1.5">
            {onChange && (
              <Button variant="ghost" size="sm" onClick={onChange}>
                {t('result.facts.change')}
              </Button>
            )}
            {onConfirm && (
              <Button size="sm" onClick={onConfirm}>
                {t('result.facts.confirm')}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
