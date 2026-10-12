import { useId, useState, type JSX, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Language } from '@/i18n'
import { cn } from '@/lib/utils'

// Each language's own quotation marks.
const QUOTE_MARKS: Record<Language, readonly [string, string]> = {
  en: ['“', '”'],
  de: ['„', '“'],
}

/** A quote longer than this many characters (about five lines in a step card) opens shortened. */
const SHORTEN_ABOVE_CHARS = 400
/** A shortened quote shows its words up to the last space within this many characters. */
const OPENING_CHARS = 300

/** The opening of a long quote, cut at a word boundary, or null when the quote is short enough
 *  to show whole. The words are never changed, only cut (components.md › Citation). */
function quoteOpening(quote: string): string | null {
  if (quote.length <= SHORTEN_ABOVE_CHARS) return null
  const cut = quote.lastIndexOf(' ', OPENING_CHARS)
  return quote.slice(0, cut > 0 ? cut : OPENING_CHARS).trimEnd()
}

export type CitationProps = {
  /** The provision's exact words, never paraphrased. Quotation marks are added. */
  children: string
  /** The language the quoted text is in: the official text the words come from. */
  language: Language
  /** Where it comes from, e.g. "Art. 3(1), Regulation (EU) 2024/1689, English". */
  source?: ReactNode
  className?: string
}

/**
 * A provision quoted word for word, in Newsreader: the Act's own voice. On a German screen, a quote
 * that exists only in English keeps its English words and says so (decision 026, item 23): Klar never
 * translates legal text. A long quote opens with its first words and an ellipsis; a button shows the
 * whole text and hides it again.
 */
export function Citation({ children, language, source, className }: CitationProps): JSX.Element {
  const { t, i18n } = useTranslation()
  const quoteId = useId()
  const [isExpanded, setIsExpanded] = useState(false)
  const isEnglishOnly = i18n.resolvedLanguage === 'de' && language === 'en'
  const [open, close] = QUOTE_MARKS[language]
  const opening = quoteOpening(children)
  const isShortened = opening !== null && !isExpanded
  const shown = isShortened ? `${opening} …` : children
  return (
    <figure
      className={cn(
        'm-0 flex flex-col gap-2 rounded-card-small bg-white/60 px-[18px] py-3.5 shadow-[inset_0_0_0_1px_var(--color-hairline)]',
        className,
      )}
    >
      <blockquote id={quoteId} lang={language} className="m-0 font-serif text-quote text-ink-2">
        <p className="m-0">
          {/* A mark the official text already has isn't doubled: the German Art. 3 Nr. 4
              opens with its own „Betreiber“. */}
          {shown.startsWith(open) ? null : open}
          {shown}
          {shown.endsWith(close) ? null : close}
        </p>
      </blockquote>
      {opening !== null && (
        <button
          type="button"
          aria-expanded={isExpanded}
          aria-controls={quoteId}
          onClick={() => {
            setIsExpanded((previous) => !previous)
          }}
          className="cursor-pointer self-start border-0 bg-transparent p-0 text-label text-lens-blue hover:underline"
        >
          {isExpanded ? t('citation.showLess') : t('citation.showFull')}
        </button>
      )}
      {isEnglishOnly && (
        <p className="m-0 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-micro text-slate">
          <span className="inline-flex h-[22px] items-center rounded-tag bg-white/60 px-2 text-xs font-semibold text-ink-2 shadow-[inset_0_0_0_1px_var(--color-border-subtle)]">
            {t('citation.englishOnly.tag')}
          </span>
          <span>{t('citation.englishOnly.explanation')}</span>
        </p>
      )}
      {source && <figcaption className="text-micro text-slate">{source}</figcaption>}
    </figure>
  )
}
