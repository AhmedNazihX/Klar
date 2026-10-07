import { Link, type LinkProps } from '@tanstack/react-router'
import type { JSX, ReactNode } from 'react'

export type ObligationItemProps = {
  /** The duty as an action the user takes ("Keep the logs it creates for at least six months"). */
  label: string
  /** The article, e.g. "Art. 26(2)"; never truncated. */
  reference: ReactNode
  /** A line under the duty: its condition, or when it applies. */
  note?: ReactNode
  /** A tag beside the note, e.g. "Art. 111(2)". */
  tag?: ReactNode
  /** The duty's draft document, if there is one. */
  docLabel?: ReactNode
  docTo?: LinkProps['to']
  /** Informational lines get no checkbox: there is nothing to tick off. */
  isInformational?: boolean
  /** The article column: 86 px in English, at least 112 px in German (localisation.md). */
  referenceWidth?: number
}

const DEFAULT_REFERENCE_WIDTH = 86

/** One duty on the to-do list: a checkbox, the duty in plain words, its draft document and the
 *  article. Wrap items in a `<ul>`. */
export function ObligationItem({
  label,
  reference,
  note,
  tag,
  docLabel,
  docTo,
  isInformational = false,
  referenceWidth = DEFAULT_REFERENCE_WIDTH,
}: ObligationItemProps): JSX.Element {
  return (
    <li className="flex min-h-13 items-center gap-3.5 border-t border-hairline py-2.5">
      {isInformational ? (
        <span aria-hidden="true" className="size-5 shrink-0" />
      ) : (
        <input
          type="checkbox"
          aria-label={label}
          className="size-5 shrink-0 cursor-pointer accent-lens-blue"
        />
      )}
      <span className="flex min-w-0 grow flex-col gap-1">
        <span className="text-body-small font-medium text-ink">{label}</span>
        {(note ?? tag) && (
          <span className="flex flex-wrap items-center gap-2 text-caption font-normal text-slate">
            {note}
            {tag && (
              <span className="inline-flex h-[22px] items-center rounded-tag bg-white/60 px-2 text-xs font-semibold whitespace-nowrap text-ink-2 shadow-[inset_0_0_0_1px_var(--color-border-subtle)]">
                {tag}
              </span>
            )}
          </span>
        )}
      </span>
      {docLabel && docTo && (
        <Link
          to={docTo}
          className="shrink-0 text-label whitespace-nowrap text-lens-blue no-underline hover:underline"
        >
          {docLabel}
        </Link>
      )}
      <span
        className="shrink-0 text-right text-caption font-normal whitespace-nowrap text-slate"
        style={{ minWidth: referenceWidth }}
      >
        {reference}
      </span>
    </li>
  )
}
