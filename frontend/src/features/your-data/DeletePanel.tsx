import type { UseMutationResult } from '@tanstack/react-query'
import { useId, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { GlassPanel } from '@/components/GlassPanel'
import { supabase } from '@/lib/supabase'

import { DANGER_BUTTON_CLASS } from './danger-button'
import { DeleteDialog } from './DeleteDialog'

/** "Delete my data": what goes, that it can't be undone, and the button that opens the dialog. */
export function DeletePanel({
  deletion,
}: {
  deletion: UseMutationResult<void, unknown, void>
}): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex flex-col gap-3.5 p-6.5 ring-[1.5px] ring-risk-prohibited-ring"
    >
      <h2 id={headingId} className="m-0 text-heading-panel text-risk-prohibited">
        {t('yourData.delete.heading')}
      </h2>
      <p className="m-0 text-label font-normal text-ink-2">{t('yourData.delete.body')}</p>
      <div className="mt-auto">
        <Button
          variant="ghost"
          disabled={supabase === null}
          className={DANGER_BUTTON_CLASS}
          onClick={() => setIsDialogOpen(true)}
        >
          {t('yourData.delete.button')}
        </Button>
      </div>
      <DeleteDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        deletion={deletion}
      />
    </GlassPanel>
  )
}
