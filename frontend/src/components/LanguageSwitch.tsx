import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { SUPPORTED_LANGUAGES, type Language } from '@/i18n'
import { cn } from '@/lib/utils'

const SHORT_LABEL: Record<Language, string> = { en: 'EN', de: 'DE' }

/** The EN/DE segmented switch from the artboards. The choice is remembered in localStorage. */
export function LanguageSwitch({ className }: { className?: string }): JSX.Element {
  const { t, i18n } = useTranslation()
  const current = i18n.resolvedLanguage
  return (
    <div
      role="group"
      aria-label={t('language.label')}
      className={cn('flex shrink-0 rounded-full p-[3px] glass-thin', className)}
    >
      {SUPPORTED_LANGUAGES.map((language) => {
        const isActive = language === current
        return (
          <button
            key={language}
            type="button"
            lang={language}
            aria-pressed={isActive}
            onClick={() => void i18n.changeLanguage(language)}
            className={cn(
              'h-[34px] rounded-full px-3 text-sm transition-colors',
              isActive
                ? 'bg-white font-semibold text-ink shadow-[0_1px_3px_rgb(15_27_45/0.16)]'
                : 'bg-transparent font-medium text-slate hover:text-ink',
            )}
          >
            <span aria-hidden="true">{SHORT_LABEL[language]}</span>
            <span className="sr-only">{t(`language.${language}`)}</span>
          </button>
        )
      })}
    </div>
  )
}
