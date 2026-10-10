import { useId, useState, type JSX, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

export type ChatCitation = {
  /** A stable key: the provision's document and id. */
  id: string
  /** The chip, e.g. "Art. 26(11)". */
  label: string
  /** What opens under the message when the chip is pressed: the quoted provision. */
  quote: ReactNode
}

export type ChatMessageProps = {
  from: 'user' | 'klar'
  /** Who speaks, for screen readers ("You", "Klar"). */
  authorLabel: string
  children: ReactNode
  /** The provisions Klar's answer rests on, as chips; each opens its quote. */
  citations?: readonly ChatCitation[]
  /** The chips' group name, e.g. "Provisions cited". */
  citationsLabel?: string
  /** A line under the answer in micro type, e.g. why no provision is cited. */
  note?: ReactNode
}

/**
 * One turn of a conversation (components.md › ChatMessage): the user's question in a Lens blue
 * bubble on the right, Klar's answer in glass on the left with the provisions it rests on as
 * chips. A chip opens the quoted provision under the answer. Text only: the model's words are
 * never rendered as HTML.
 */
export function ChatMessage({
  from,
  authorLabel,
  children,
  citations = [],
  citationsLabel,
  note,
}: ChatMessageProps): JSX.Element {
  const [openId, setOpenId] = useState<string | null>(null)
  const quoteId = useId()
  const open = citations.find((citation) => citation.id === openId)
  if (from === 'user') {
    return (
      <div className="flex max-w-[min(520px,88%)] flex-col self-end rounded-[20px_20px_6px_20px] bg-lens-blue px-4 py-3 text-body-small break-words whitespace-pre-line text-white shadow-[0_10px_24px_-14px_rgb(45_75_224/0.7)]">
        <span className="sr-only">{authorLabel}: </span>
        {children}
      </div>
    )
  }
  return (
    <div className="flex max-w-[min(640px,100%)] flex-col gap-2.5 self-start rounded-[20px_20px_20px_6px] px-[18px] py-4 text-body-small break-words text-ink glass-thin">
      <span className="sr-only">{authorLabel}: </span>
      {children}
      {citations.length > 0 && (
        <ul
          aria-label={citationsLabel}
          className="m-0 flex min-w-0 list-none flex-wrap gap-1.5 p-0"
        >
          {citations.map((citation) => (
            // A long guideline name wraps inside its chip, so a phone never scrolls sideways.
            <li key={citation.id} className="max-w-full min-w-0">
              <button
                type="button"
                aria-expanded={openId === citation.id}
                aria-controls={openId === citation.id ? quoteId : undefined}
                onClick={() => {
                  setOpenId((current) => (current === citation.id ? null : citation.id))
                }}
                className={cn(
                  'inline-flex min-h-6 max-w-full cursor-pointer items-center rounded-pill border-0 bg-white/75 px-2.5 py-0.5 text-left text-xs font-medium break-words text-ink-2 shadow-[inset_0_0_0_1px_rgb(15_27_45/0.14)] hover:bg-white',
                  openId === citation.id && 'shadow-[inset_0_0_0_1px_var(--color-lens-blue)]',
                )}
              >
                {citation.label}
              </button>
            </li>
          ))}
        </ul>
      )}
      {open && <div id={quoteId}>{open.quote}</div>}
      {note && <p className="m-0 text-micro text-slate">{note}</p>}
    </div>
  )
}
