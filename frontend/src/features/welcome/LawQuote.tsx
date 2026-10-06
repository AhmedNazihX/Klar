import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { Citation } from '@/components/Citation'
import type { Language } from '@/i18n'

/** The provisions this screen quotes; the words live in the locales (welcome.law), per language. */
export type QuotedProvision = 'art99_3' | 'art99_6' | 'art99_6a' | 'art2_1_c' | 'art22_1'

/**
 * One provision word for word in the reader's language, from the official text on EUR-Lex, with
 * its source line. All but Art. 99(6a) read the same in the original and the amended Act; Art.
 * 99(6a) exists only in the amended text, and only screens under the amended text quote it.
 */
export function LawQuote({ provision }: { provision: QuotedProvision }): JSX.Element {
  const { t, i18n } = useTranslation()
  const language: Language = i18n.resolvedLanguage === 'de' ? 'de' : 'en'
  return (
    <Citation language={language} source={t(`welcome.law.${provision}.source`)}>
      {t(`welcome.law.${provision}.quote`)}
    </Citation>
  )
}
