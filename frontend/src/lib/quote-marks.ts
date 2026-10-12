import type { Language } from '@/i18n'

/** Each language's own quotation marks, the ones a quote is framed in. */
export const QUOTE_MARKS: Readonly<Record<Language, readonly [string, string]>> = {
  en: ['“', '”'],
  de: ['„', '“'],
}

// The marks a quote inside a quote takes: „…“ becomes ‚…‘ in German, “…” becomes ‘…’ in English.
const NESTED_MARKS: Readonly<Record<Language, readonly [string, string]>> = {
  en: ['‘', '’'],
  de: ['‚', '‘'],
}

/** `text` with its own double quotation marks in the nested form, so the outer marks around it
 *  always frame it (the German Art. 3 Nr. 4 opens with „Betreiber“: „‚Betreiber‘ eine …“). Only
 *  the double marks of `language`, the text's own, change; apostrophes and single marks stay. */
export function nestQuotes(text: string, language: Language): string {
  const [open, close] = QUOTE_MARKS[language]
  const [nestedOpen, nestedClose] = NESTED_MARKS[language]
  return text.replaceAll(open, nestedOpen).replaceAll(close, nestedClose)
}
