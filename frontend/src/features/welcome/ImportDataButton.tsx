import type { ChangeEvent, JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { buttonVariants } from '@/components/button-variants'
import { useImportUserData } from '@/hooks/use-import-user-data'
import { supabase } from '@/lib/supabase'
import { cn } from '@/lib/utils'

import { WriteFailureMessage } from './WriteFailureMessage'

const FOCUS_RING = 'has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-lens-blue'

/**
 * "Import your data": restores a file exported from Your data (import_my_data). Nothing is
 * classified again. The label is the control, so the file input keeps its keyboard focus.
 * `link` (Welcome's tools panel) is a centred link with a hint under it; `ghost` (the Inventory's
 * header) is a ghost button for a button row, without the hint. Your data passes `className` to
 * align it with its panel.
 */
export function ImportDataButton({
  variant = 'link',
  className,
}: {
  variant?: 'link' | 'ghost'
  className?: string
}): JSX.Element {
  const { t } = useTranslation()
  const importData = useImportUserData()
  const isGhost = variant === 'ghost'

  function chooseFile(event: ChangeEvent<HTMLInputElement>): void {
    const file = event.target.files?.[0]
    // Cleared, so choosing the same file again still imports it.
    event.target.value = ''
    if (file) importData.mutate(file)
  }

  return (
    <div className={cn('flex flex-col gap-2', isGhost ? 'items-end' : 'items-center', className)}>
      <label
        className={cn(
          FOCUS_RING,
          isGhost
            ? buttonVariants({ variant: 'ghost' })
            : 'cursor-pointer rounded-md text-body-small font-medium text-lens-blue hover:underline',
        )}
      >
        <input
          type="file"
          accept=".json,application/json"
          className="sr-only"
          disabled={importData.isPending || supabase === null}
          onChange={chooseFile}
        />
        {importData.isPending ? t('welcome.tools.importing') : t('welcome.tools.import')}
      </label>
      {!isGhost && <p className="m-0 text-caption text-slate">{t('welcome.tools.importHint')}</p>}
      {importData.isSuccess && (
        <p role="status" className="m-0 text-body-small text-ink">
          {t('welcome.tools.imported', { count: importData.data.systems })}
        </p>
      )}
      {importData.isError && <WriteFailureMessage error={importData.error} kind="import" />}
    </div>
  )
}
