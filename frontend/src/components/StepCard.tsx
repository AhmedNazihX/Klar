import { useId, useState, type JSX, type ReactNode } from 'react'

import type { Language } from '@/i18n'
import { cn } from '@/lib/utils'

import { Citation } from './Citation'
import { EvidenceTag } from './EvidenceTag'
import type { Evidence } from './pill-kinds'

export type StepCardFact = { id: string; text: ReactNode; evidence: Evidence }
export type StepCardQuote = { id: string; text: string; language: Language; source: ReactNode }

/** A step that didn't decide the class names its provisions instead of quoting them; the quotes
 *  open on request. */
export type StepCardQuotesClosed = {
  /** e.g. "Checked: Art. 50". */
  checked: ReactNode
  /** e.g. "Show the provision" (or "provisions" for several). */
  toggleLabel: string
}

export type StepCardProps = {
  /** e.g. "3 High-risk". */
  name: ReactNode
  /** h2 on the Reviewer view, h3 inside a section. */
  headingLevel?: 2 | 3
  /** A RiskPill or StatusPill. */
  outcome?: ReactNode
  reference?: ReactNode
  decisionLabel: string
  decision?: ReactNode
  factLabel: string
  facts?: readonly StepCardFact[]
  quotes?: readonly StepCardQuote[]
  /** Set on a step that didn't decide the class: its quotes stay behind a toggle. */
  quotesClosed?: StepCardQuotesClosed
  /** The one card that decided a High-risk result: an orange ring. */
  highlight?: boolean
  /** Anything else the step carries, under the quotes (an open question, a duty list). */
  children?: ReactNode
  className?: string
}

function Quotes({ quotes, id }: { quotes: readonly StepCardQuote[]; id?: string }): JSX.Element {
  return (
    <div id={id} className={cn('grid gap-3', quotes.length === 2 && 'lg:grid-cols-2')}>
      {quotes.map((quote) => (
        <Citation
          key={quote.id}
          language={quote.language}
          source={quote.source}
          className="min-w-0"
        >
          {quote.text}
        </Citation>
      ))}
    </div>
  )
}

/** The provisions a step checked, named in one line, with a toggle that shows their quotes. */
function ClosedQuotes({
  quotes,
  closed,
}: {
  quotes: readonly StepCardQuote[]
  closed: StepCardQuotesClosed
}): JSX.Element {
  const quotesId = useId()
  const [isOpen, setIsOpen] = useState(false)
  return (
    <>
      <p className="m-0 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-body-small text-slate">
        <span>{closed.checked}</span>
        <button
          type="button"
          aria-expanded={isOpen}
          aria-controls={quotesId}
          onClick={() => {
            setIsOpen((previous) => !previous)
          }}
          className="cursor-pointer border-0 bg-transparent p-0 text-label text-lens-blue hover:underline"
        >
          {closed.toggleLabel}
        </button>
      </p>
      {isOpen ? <Quotes quotes={quotes} id={quotesId} /> : <div id={quotesId} hidden />}
    </>
  )
}

/**
 * One step of the classification, expanded for a reviewer: the decision, the facts it rests on
 * with their evidence tags, and the quoted provisions (side by side when there are two). Only the
 * step that decided the class shows its quotes open; another names them (`quotesClosed`) and
 * quotes them on request. The consumer provides every text; the card never writes legal content
 * itself.
 */
export function StepCard({
  name,
  headingLevel = 3,
  outcome,
  reference,
  decisionLabel,
  decision,
  factLabel,
  facts = [],
  quotes = [],
  quotesClosed,
  highlight = false,
  children,
  className,
}: StepCardProps): JSX.Element {
  const Heading = headingLevel === 2 ? 'h2' : 'h3'
  return (
    <article
      data-highlight={highlight || undefined}
      className={cn(
        'flex min-w-0 flex-col gap-3.5 rounded-tile px-6 py-5.5 glass',
        highlight && 'shadow-highlight-high',
        className,
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <Heading className="m-0 text-heading-small text-ink">{name}</Heading>
          {outcome}
        </div>
        {reference && <span className="text-caption font-semibold text-ink">{reference}</span>}
      </header>
      <dl className="m-0 grid grid-cols-1 gap-x-4 gap-y-2.5 text-body-small md:grid-cols-[150px_minmax(0,1fr)]">
        {decision && (
          <>
            <dt className="text-slate">{decisionLabel}</dt>
            <dd className="m-0 text-ink">{decision}</dd>
          </>
        )}
        {facts.length > 0 && (
          <>
            <dt className="text-slate">{factLabel}</dt>
            <dd className="m-0 flex flex-col gap-1.5">
              {facts.map((fact) => (
                <span key={fact.id} className="flex flex-wrap items-center gap-2.5 text-ink">
                  {fact.text}
                  <EvidenceTag kind={fact.evidence} />
                </span>
              ))}
            </dd>
          </>
        )}
      </dl>
      {quotes.length > 0 &&
        (quotesClosed ? (
          <ClosedQuotes quotes={quotes} closed={quotesClosed} />
        ) : (
          <Quotes quotes={quotes} />
        ))}
      {children}
    </article>
  )
}
