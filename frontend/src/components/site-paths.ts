import type { Language } from '@/i18n'

/** The landing page in each language: English at `/`, German at `/de` (P16). */
export const LANDING_PATH = { en: '/', de: '/de' } as const satisfies Record<Language, string>

/** The landing page for `language`, falling back to English for anything else. */
export function landingPathFor(language: string | undefined): (typeof LANDING_PATH)[Language] {
  return language === 'de' ? LANDING_PATH.de : LANDING_PATH.en
}
