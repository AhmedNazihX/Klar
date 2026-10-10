import { Link } from '@tanstack/react-router'
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
  /** The duty's draft document, if there is one: the link's text and the document's id. */
  docLabel?: ReactNode
  documentId?: string | null
  /** The tool the document belongs to: documents are keyed by tool and template (P9). */
  toolId?: string
  /** Informational lines get no checkbox: there is nothing to tick off. */
  isInformational?: boolean
  /** The article column: 86 px in English, at least 112 px in German (localisation.md). */
  referenceWidth?: number
  /** The duty is ticked off; with `onCheckedChange`, the box shows the saved tick. */
  checked?: boolean
  /** Called with the box's new state when the user ticks or clears it. */
  onCheckedChange?: (checked: boolean) => void
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
  documentId,
  toolId,
  isInformational = false,
  referenceWidth = DEFAULT_REFERENCE_WIDTH,
  checked,
  onCheckedChange,
}: ObligationItemProps): JSX.Element {
  return (
    <li className="@container border-t border-hairline">
      <div className="grid min-h-13 grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3.5 gap-y-1.5 py-2.5 @md:grid-cols-[auto_minmax(0,1fr)_auto]">
        {isInformational ? (
          <span aria-hidden="true" className="size-5 shrink-0" />
        ) : (
          // The 20 px box sits in a 44 px label, its touch target; the negative margin keeps the
          // row's layout as drawn.
          <label className="-m-3 flex size-11 shrink-0 cursor-pointer items-center justify-center">
            <input
              type="checkbox"
              aria-label={label}
              checked={onCheckedChange ? (checked ?? false) : undefined}
              onChange={onCheckedChange && ((event) => onCheckedChange(event.target.checked))}
              className="size-5 cursor-pointer accent-lens-blue"
            />
          </label>
        )}
        <span className="flex min-w-0 flex-col gap-1">
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
        {/* In a narrow row (a phone) the draft link and the article sit under the duty, so the
            duty keeps its width and the article stays whole. */}
        <span className="col-start-2 flex flex-wrap items-center gap-x-3.5 gap-y-1 @md:col-start-3 @md:row-start-1 @md:flex-nowrap">
          {docLabel && documentId && (
            <Link
              to="/app/documents/$documentId"
              params={{ documentId }}
              search={{ tool: toolId }}
              className="inline-flex min-h-11 shrink-0 items-center text-label whitespace-nowrap text-lens-blue no-underline hover:underline md:min-h-0"
            >
              {docLabel}
            </Link>
          )}
          <span
            className="shrink-0 text-caption font-normal whitespace-nowrap text-slate @md:text-right"
            style={{ minWidth: referenceWidth }}
          >
            {reference}
          </span>
        </span>
      </div>
    </li>
  )
}
