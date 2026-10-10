import { useEffect, useRef, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { Button } from '@/components/Button'
import { ChecksPanel } from '@/features/documents/ChecksPanel'
import { DraftView } from '@/features/documents/DraftView'
import { useLanguage } from '@/hooks/use-language'
import { useVendorLetter } from '@/hooks/use-vendor-letter'

/** The drafted letter, asked for only while the dialog is open. */
function LetterBody({
  toolId,
  result,
}: {
  toolId: string
  result: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const letter = useVendorLetter(toolId, result, language)
  if (letter.isPending) {
    return (
      <p role="status" className="m-0 text-body-small text-slate">
        {t('prohibited.letter.drafting')}
      </p>
    )
  }
  if (letter.isError) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3">
        <p className="m-0 text-body-small text-ink">{t('prohibited.letter.failed')}</p>
        <Button variant="ghost" size="sm" onClick={() => void letter.refetch()}>
          {t('prohibited.letter.tryAgain')}
        </Button>
      </div>
    )
  }
  return (
    <>
      <DraftView
        document={letter.data.document}
        isSkeleton={false}
        toFillIn={t('prohibited.letter.toFillIn')}
      />
      <ChecksPanel checks={letter.data.checks} isSkeleton={false} />
    </>
  )
}

/**
 * "Draft a message": P28's vendor letter for a prohibited result, drafted by the API from the
 * result (the Art. 5(1) points it quotes come from the corpus, decision 031), labelled DRAFT and
 * carrying the notice. The recipient, the tool's name and the sender are the user's to fill in.
 * A native modal dialog: focus stays inside, Escape closes it and focus goes back to the button
 * that opened it.
 */
export function VendorLetterDialog({
  isOpen,
  onClose,
  toolId,
  result,
}: {
  isOpen: boolean
  /** Called when the dialog closes: Close, Escape, or the browser closing it. */
  onClose: () => void
  toolId: string
  result: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  const dialogRef = useRef<HTMLDialogElement>(null)

  // The open state lives in React; the browser's modal (top layer, inert page) follows it.
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (isOpen && !dialog.open) dialog.showModal()
    if (!isOpen && dialog.open) dialog.close()
  }, [isOpen])

  return (
    <dialog
      ref={dialogRef}
      aria-label={t('prohibited.letter.label')}
      onClose={onClose}
      className="m-auto max-h-[calc(100dvh-32px)] w-[min(760px,calc(100vw-32px))] overflow-y-auto rounded-card border border-white/80 bg-mist p-5 text-ink shadow-glass backdrop:bg-ink/28 backdrop:backdrop-blur-sm md:p-7"
    >
      {isOpen && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <p className="m-0 max-w-[560px] text-body-small text-ink-2">
              {t('prohibited.letter.intro')}
            </p>
            <Button variant="ghost" size="sm" onClick={() => dialogRef.current?.close()}>
              {t('prohibited.letter.close')}
            </Button>
          </div>
          <LetterBody toolId={toolId} result={result} />
        </div>
      )}
    </dialog>
  )
}
