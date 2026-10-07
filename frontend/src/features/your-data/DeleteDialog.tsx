import type { UseMutationResult } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState, type JSX, type SyntheticEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { useMyDataCounts } from '@/hooks/use-my-data-counts'
import type { MyDataCounts } from '@/lib/user-data'

import { DANGER_BUTTON_CLASS } from './danger-button'

type DeleteDialogProps = {
  isOpen: boolean
  /** Called when the dialog closes: Cancel, Escape, or the browser closing it. */
  onClose: () => void
  /** The screen's deletion, so its outcome outlives the dialog. */
  deletion: UseMutationResult<void, unknown, void>
}

// The kinds the dialog counts, in the order "What Klar keeps" lists them. The company profile,
// one at most, is named without a number.
const COUNTED_KINDS = [
  'systems',
  'classifications',
  'interviewAnswers',
  'dutyProgress',
] as const satisfies readonly (keyof MyDataCounts)[]

// The list's locale per app language: British English, with no comma before "and", as the app's
// other English lists. Any other language lists in its own locale.
const LIST_LOCALES: Readonly<Partial<Record<string, string>>> = { en: 'en-GB' }

/**
 * What the deletion takes, from the counts the screen has loaded: "Klar will delete 2 tools,
 * 3 results … for good", only the kinds the user has. Without counts (loading, failed, or nothing
 * stored) it names the kinds instead.
 */
function useLossText(): string {
  const { t, i18n } = useTranslation()
  const counts = useMyDataCounts().data
  if (!counts) return t('yourData.delete.dialogBody')
  const counted = COUNTED_KINDS.filter((kind) => counts[kind] > 0).map((kind) =>
    t(`yourData.delete.lost.${kind}`, { count: counts[kind] }),
  )
  const items =
    counts.companyProfiles > 0 ? [...counted, t('yourData.delete.lost.companyProfile')] : counted
  if (items.length === 0) return t('yourData.delete.dialogBody')
  const listLocale = LIST_LOCALES[i18n.language] ?? i18n.language
  const list = new Intl.ListFormat(listLocale, { type: 'conjunction' }).format(items)
  return t('yourData.delete.dialogBodyCounts', { items: list })
}

/**
 * "Delete everything?": the user types the confirmation word (DELETE, in German LÖSCHEN) before
 * the button works. A native modal dialog: opening it focuses the field (its first control),
 * focus stays inside, Escape closes it and focus goes back to the button that opened it.
 */
export function DeleteDialog({ isOpen, onClose, deletion }: DeleteDialogProps): JSX.Element {
  const { t } = useTranslation()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const bodyId = useId()
  const inputId = useId()
  const [typed, setTyped] = useState('')
  const word = t('yourData.delete.word')
  const isConfirmed = typed.trim() === word
  const lossText = useLossText()

  // The open state lives in React; the browser's modal (top layer, inert page) follows it.
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (isOpen && !dialog.open) dialog.showModal()
    if (!isOpen && dialog.open) dialog.close()
  }, [isOpen])

  function close(): void {
    setTyped('')
    // Only a failure is cleared: a success has already replaced the screen with "deleted".
    if (deletion.isError) deletion.reset()
    onClose()
  }

  function confirm(event: SyntheticEvent): void {
    event.preventDefault()
    if (isConfirmed) deletion.mutate()
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      onClose={close}
      className="m-auto w-[min(480px,calc(100vw-32px))] rounded-card border border-white/80 bg-white/96 p-7 text-ink shadow-glass backdrop:bg-ink/28 backdrop:backdrop-blur-sm"
    >
      <form onSubmit={confirm} className="flex flex-col gap-4">
        <h2 id={titleId} className="m-0 text-[22px] leading-tight font-semibold tracking-[-0.02em]">
          {t('yourData.delete.dialogTitle')}
        </h2>
        <p id={bodyId} className="m-0 text-body-small text-ink-2">
          {lossText}
        </p>
        <label htmlFor={inputId} className="text-label font-semibold">
          {t('yourData.delete.confirmLabel', { word })}
        </label>
        <input
          id={inputId}
          type="text"
          autoComplete="off"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          className="h-11.5 rounded-field border border-border-subtle bg-white px-3.5 text-body font-medium tracking-[0.04em] text-ink"
        />
        {deletion.isError && (
          <p role="alert" className="m-0 text-body-small text-risk-prohibited">
            {t('yourData.delete.failed')}
          </p>
        )}
        <div className="mt-1 flex flex-wrap justify-end gap-2.5">
          <Button variant="ghost" onClick={() => dialogRef.current?.close()}>
            {t('yourData.delete.cancel')}
          </Button>
          <Button
            type="submit"
            variant="ghost"
            disabled={!isConfirmed || deletion.isPending}
            className={DANGER_BUTTON_CLASS}
          >
            {deletion.isPending ? t('yourData.delete.pending') : t('yourData.delete.confirm')}
          </Button>
        </div>
      </form>
    </dialog>
  )
}
