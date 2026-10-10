import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { SUPPORTED_LANGUAGES, type Language } from '@/i18n'

import { SegmentedControl } from './SegmentedControl'

const SHORT_LABEL: Record<Language, string> = { en: 'EN', de: 'DE' }

/**
 * The EN/DE segmented switch from the artboards. The choice is remembered in localStorage;
 * `onChange` runs after the language changes (the site nav uses it to move between landing pages).
 * `shown` puts the pill under another language for a moment, so it can flow to the current one
 * (the German landing page on arrival).
 */
export function LanguageSwitch({
  className,
  onChange,
  shown,
}: {
  className?: string
  onChange?: (language: Language) => void
  shown?: Language
}): JSX.Element {
  const { t, i18n } = useTranslation()
  const current = SUPPORTED_LANGUAGES.find((language) => language === i18n.resolvedLanguage)
  return (
    <SegmentedControl<Language>
      label={t('language.label')}
      value={shown ?? current ?? 'en'}
      onChange={(language) => {
        void i18n.changeLanguage(language)
        onChange?.(language)
      }}
      options={SUPPORTED_LANGUAGES.map((language) => ({
        value: language,
        lang: language,
        label: (
          <>
            <span aria-hidden="true">{SHORT_LABEL[language]}</span>
            <span className="sr-only">{t(`language.${language}`)}</span>
          </>
        ),
      }))}
      className={className}
    />
  )
}
