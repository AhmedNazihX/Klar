import type { JSX, ReactNode } from 'react'

import type { Language } from '@/i18n'
import { cn } from '@/lib/utils'

import { Citation } from './Citation'
import { EvidenceTag } from './EvidenceTag'
import type { Evidence } from './pill-kinds'

export type StepCardFact = { id: string; text: ReactNode; evidence: Evidence }
export type StepCardQuote = { id: string; text: ReactNode; language: Language; source: ReactNode }

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
  /** The one card that decided a High-risk result: an orange ring. */
  highlight?: boolean
  /** Anything else the step carries, under the quotes (an open question, a duty list). */
  children?: ReactNode
  className?: string
}

/**
 * One step of the classification, expanded for a reviewer: the decision, the facts it rests on
 * with their evidence tags, and the quoted provisions (side by side when there are two). The
 * consumer provides every text; the card never writes legal content itself.
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
      {quotes.length > 0 && (
        <div className={cn('grid gap-3', quotes.length === 2 && 'lg:grid-cols-2')}>
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
      )}
      {children}
    </article>
  )
}
