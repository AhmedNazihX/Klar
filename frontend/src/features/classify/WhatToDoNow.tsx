import { useId, useState, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'

import { VendorLetterDialog } from './VendorLetterDialog'

function Step({
  number,
  children,
  action,
}: {
  number: number
  children: ReactNode
  action?: ReactNode
}): JSX.Element {
  return (
    <li className="flex min-h-13 flex-wrap items-center gap-x-3.5 gap-y-2 border-t border-hairline py-2">
      <span
        aria-hidden="true"
        className="w-3.5 shrink-0 text-[15px] font-semibold text-risk-prohibited"
      >
        {number}
      </span>
      <span className="min-w-0 flex-1 basis-[220px] text-[15px] leading-normal font-medium text-ink">
        {children}
      </span>
      {action}
    </li>
  )
}

/** "What to do now" on a prohibited result: no route to comply, so three numbered steps; the
 *  second opens P28's message to the vendor. */
export function WhatToDoNow({
  toolId,
  result,
}: {
  toolId: string
  result: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const [isLetterOpen, setIsLetterOpen] = useState(false)
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-2 px-7 py-6.5"
    >
      <h2 id={headingId} className="m-0 text-heading-panel text-ink">
        {t('prohibited.now.heading')}
      </h2>
      <p className="m-0 text-body-small text-slate">{t('prohibited.now.intro')}</p>
      <ol className="m-0 mt-2 flex list-none flex-col p-0">
        <Step number={1}>{t('prohibited.now.stop')}</Step>
        <Step
          number={2}
          action={
            <Button
              variant="ghost"
              size="sm"
              aria-haspopup="dialog"
              onClick={() => {
                setIsLetterOpen(true)
              }}
            >
              {t('prohibited.now.draftMessage')}
            </Button>
          }
        >
          {t('prohibited.now.tellVendor')}
        </Step>
        <Step number={3}>{t('prohibited.now.data')}</Step>
      </ol>
      <VendorLetterDialog
        isOpen={isLetterOpen}
        onClose={() => {
          setIsLetterOpen(false)
        }}
        toolId={toolId}
        result={result}
      />
    </GlassPanel>
  )
}
