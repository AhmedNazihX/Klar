import { useEffect, useRef, useState, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult, DraftDocument } from '@/api'
import { Button } from '@/components/Button'
import { ChecksPanel } from '@/features/documents/ChecksPanel'
import { DraftView } from '@/features/documents/DraftView'
import { useLanguage } from '@/hooks/use-language'
import { useVendorLetter } from '@/hooks/use-vendor-letter'

import { letterText } from './letter-text'

type CopyState = 'idle' | 'copied' | 'failed'

/** "Copy message": the letter as plain text on the clipboard, for the user's own email, and a
 *  line saying whether it worked (a browser can refuse the clipboard). */
function CopyMessage({ document }: { document: DraftDocument }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const [state, setState] = useState<CopyState>('idle')

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(letterText(t, document, language))
      setState('copied')
    } catch {
      // No clipboard (an insecure page) or the browser refused it: the user can still select it.
      setState('failed')
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="sm" onClick={() => void copy()}>
        {t('prohibited.letter.copy')}
      </Button>
      <span role="status" className="text-body-small text-slate">
        {state === 'copied' && t('prohibited.letter.copied')}
        {state === 'failed' && t('prohibited.letter.copyFailed')}
      </span>
    </div>
  )
}

/** The drafted letter, asked for only while the dialog is open. */
function LetterBody({
  toolId,
  toolName,
  result,
}: {
  toolId: string
  toolName: string | null
  result: ClassificationResult
}): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const letter = useVendorLetter(toolId, toolName, result, language)
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
      <CopyMessage document={letter.data.document} />
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
 * carrying the notice. It names the tool as the user named it; the recipient and the sender are
 * theirs to fill in, and "Copy message" puts it on the clipboard for their own email.
 * A native modal dialog: focus stays inside, Escape closes it and focus goes back to the button
 * that opened it.
 */
export function VendorLetterDialog({
  isOpen,
  onClose,
  toolId,
  toolName,
  result,
}: {
  isOpen: boolean
  /** Called when the dialog closes: Close, Escape, or the browser closing it. */
  onClose: () => void
  toolId: string
  /** The tool's name in the inventory, the letter's answer to "The tool"; none leaves it to fill
   *  in. */
  toolName: string | null
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
          <LetterBody toolId={toolId} toolName={toolName} result={result} />
        </div>
      )}
    </dialog>
  )
}
