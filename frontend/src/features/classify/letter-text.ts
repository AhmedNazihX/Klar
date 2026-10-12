import type { TFunction } from 'i18next'

import type { DraftDocument, DraftSection } from '@/api'
import type { Language } from '@/i18n'
import { nestQuotes } from '@/lib/quote-marks'

import { citationSource } from './result-text'

/** A quote as plain text: the corpus's words in the letter language's quotation marks (the
 *  text's own marks nested, as the Citation shows them), then its source. */
function quoteText(t: TFunction, section: DraftSection, language: Language): string[] {
  return (section.quotes ?? []).map((quote) =>
    t('prohibited.letter.copyQuote', {
      quote: nestQuotes(quote.quote, quote.language),
      source: citationSource(t, quote, language),
    }),
  )
}

/** One section as plain text: its heading, its paragraphs and quotes, or the to-fill-in marker
 *  in square brackets where the user still has to write it. */
function sectionText(t: TFunction, section: DraftSection, language: Language): string {
  const body =
    section.status === 'drafted'
      ? [...(section.paragraphs ?? []), ...quoteText(t, section, language)]
      : [`[${t('prohibited.letter.toFillIn')}]`]
  return [section.heading, ...body].join('\n')
}

/**
 * The drafted letter as plain text, for "Copy message": the title and its DRAFT stamp, in the
 * screen's language as the dialog shows it (the document's own label is English), each
 * section in order, and the notice, blocks set apart by a blank line. The user pastes it into
 * their own email, so it carries what the dialog shows and nothing more.
 */
export function letterText(t: TFunction, document: DraftDocument, language: Language): string {
  return [
    `${document.title} (${t('status.draft')})`,
    ...document.sections.map((section) => sectionText(t, section, language)),
    `${t('documents.preparedWith')} ${document.disclaimer}`,
  ].join('\n\n')
}
