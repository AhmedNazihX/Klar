import { useTranslation } from 'react-i18next'

import type { Language } from '@/i18n'

/** The language the screen is shown in: German when chosen, English otherwise. */
export function useLanguage(): Language {
  const { i18n } = useTranslation()
  return i18n.resolvedLanguage === 'de' ? 'de' : 'en'
}
