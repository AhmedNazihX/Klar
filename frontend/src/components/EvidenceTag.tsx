import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import type { Evidence } from './pill-kinds'

// The glyph carries the meaning, not colour: filled dot for Stated, half dot for Inferred, ring for
// Assumed. Drawn as in the system's own EvidenceTag.
function EvidenceGlyph({ kind }: { kind: Evidence }): JSX.Element {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" className="shrink-0">
      {kind === 'stated' ? (
        <circle cx="5" cy="5" r="4" fill="currentColor" />
      ) : (
        <circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
      )}
      {kind === 'inferred' && <path d="M5 1.5a3.5 3.5 0 0 1 0 7z" fill="currentColor" />}
    </svg>
  )
}

export type EvidenceTagProps = {
  kind: Evidence
  /** Label override; defaults to the translated kind. */
  children?: ReactNode
  className?: string
}

/** Where a fact came from, so a reader can challenge it. Neutral: it never competes with risk colours. */
export function EvidenceTag({ kind, children, className }: EvidenceTagProps): JSX.Element {
  const { t } = useTranslation()
  return (
    <span
      data-evidence={kind}
      className={cn(
        'inline-flex h-[22px] items-center gap-[5px] rounded-tag bg-white/60 px-2 text-xs leading-none font-semibold whitespace-nowrap text-ink-2 shadow-[inset_0_0_0_1px_var(--color-border-subtle)]',
        className,
      )}
    >
      <EvidenceGlyph kind={kind} />
      {children ?? t(`evidence.${kind}`)}
    </span>
  )
}
