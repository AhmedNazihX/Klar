import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { Button } from './Button'
import { EvidenceTag } from './EvidenceTag'
import type { Evidence } from './pill-kinds'

export type FactCardProps = {
  fact: ReactNode
  evidence: Evidence
  /** Assumed facts offer Change; the consumer handles it. Confirm comes with the follow-up
   *  loop (P5b). */
  onChange?: () => void
}

/** One fact a result rests on, with its evidence tag. Assumed cards get a Lens blue ring so they
 *  are found first, and Change. */
export function FactCard({ fact, evidence, onChange }: FactCardProps): JSX.Element {
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
        {isAssumed && onChange && (
          <Button variant="ghost" size="sm" className="shrink-0" onClick={onChange}>
            {t('result.facts.change')}
          </Button>
        )}
      </div>
    </div>
  )
}
