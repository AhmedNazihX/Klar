import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Language } from '@/i18n'
import { cn } from '@/lib/utils'

// Each language's own quotation marks.
const QUOTE_MARKS: Record<Language, readonly [string, string]> = {
  en: ['“', '”'],
  de: ['„', '“'],
}

export type CitationProps = {
  /** The provision's exact words, never paraphrased. Quotation marks are added. */
  children: ReactNode
  /** The language the quoted text is in: the official text the words come from. */
  language: Language
  /** Where it comes from, e.g. "Art. 3(1), Regulation (EU) 2024/1689, English". */
  source?: ReactNode
  className?: string
}

/**
 * A provision quoted word for word, in Newsreader: the Act's own voice. On a German screen, a quote
 * that exists only in English keeps its English words and says so (decision 026, item 23): Klar never
 * translates legal text.
 */
export function Citation({ children, language, source, className }: CitationProps): JSX.Element {
  const { t, i18n } = useTranslation()
  const isEnglishOnly = i18n.resolvedLanguage === 'de' && language === 'en'
  const [open, close] = QUOTE_MARKS[language]
  return (
    <figure
      className={cn(
        'm-0 flex flex-col gap-2 rounded-card-small bg-white/60 px-[18px] py-3.5 shadow-[inset_0_0_0_1px_var(--color-hairline)]',
        className,
      )}
    >
      <blockquote lang={language} className="m-0 font-serif text-quote text-ink-2">
        <p className="m-0">
          {open}
          {children}
          {close}
        </p>
      </blockquote>
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
