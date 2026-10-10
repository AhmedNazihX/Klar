// i18next set-up: English and German, English as the fallback. The chosen language is kept in
// localStorage; on a first visit the browser's language decides.
import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import de from './locales/de.json'
import en from './locales/en.json'

export const SUPPORTED_LANGUAGES = ['en', 'de'] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]

/** The locale `Intl` formats each language in (dates, lists): British English and German. */
export const LANGUAGE_LOCALES: Readonly<Record<Language, string>> = { en: 'en-GB', de: 'de-DE' }

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

function readSavedLanguage(): string | null {
  try {
    return window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
  } catch {
    return null // Storage is blocked: the detector can't save a language either.
  }
}

function restoreSavedLanguage(saved: string | null): void {
  try {
    if (saved === null) window.localStorage.removeItem(LANGUAGE_STORAGE_KEY)
    else window.localStorage.setItem(LANGUAGE_STORAGE_KEY, saved)
  } catch {
    // Storage is blocked: the detector couldn't save over the choice, so there is nothing to undo.
  }
}

/**
 * Shows the site in `language` without saving it as the visitor's choice. A landing page's address
 * picks its language (`/` English, `/de` German), but only the EN/DE switch changes the language
 * the app opens in next time (P16): i18next saves every change, so the saved value is put back.
 */
export async function showLanguage(language: Language): Promise<void> {
  if (i18n.resolvedLanguage === language) return
  const saved = readSavedLanguage()
  await i18n.changeLanguage(language)
  restoreSavedLanguage(saved)
}

// Keep <html lang> in step, so screen readers and hyphenation use the right language.
function syncDocumentLanguage(language: string): void {
  document.documentElement.lang = language
}
syncDocumentLanguage(i18n.resolvedLanguage ?? 'en')
i18n.on('languageChanged', syncDocumentLanguage)

export default i18n
