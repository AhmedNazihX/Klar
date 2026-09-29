// i18next set-up: English and German, English as the fallback. The chosen language is kept in
// localStorage; on a first visit the browser's language decides.
import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import de from './locales/de.json'
import en from './locales/en.json'

export const SUPPORTED_LANGUAGES = ['en', 'de'] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]

export const LANGUAGE_STORAGE_KEY = 'klar.language'
const resources = { en: { translation: en }, de: { translation: de } } as const

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    supportedLngs: SUPPORTED_LANGUAGES,
    load: 'languageOnly',
    initAsync: false,
    interpolation: { escapeValue: false }, // React escapes already.
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: LANGUAGE_STORAGE_KEY,
    },
  })

// Keep <html lang> in step, so screen readers and hyphenation use the right language.
function syncDocumentLanguage(language: string): void {
  document.documentElement.lang = language
}
syncDocumentLanguage(i18n.resolvedLanguage ?? 'en')
i18n.on('languageChanged', syncDocumentLanguage)

export default i18n
