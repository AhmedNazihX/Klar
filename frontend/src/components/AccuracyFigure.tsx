import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { LANGUAGE_LOCALES, type Language } from '@/i18n'
import type { AccuracyFigure as Figure } from '@/lib/accuracy'

import { Placeholder } from './Placeholder'

/**
 * One published rate from accuracy.json as a percentage in the page's language, or the marked
 * `[—%]` while it is unmeasured (components.md › MetricTile: never invent a figure).
 */
export function AccuracyFigure({ figure }: { figure: Figure | null }): JSX.Element {
  const { t, i18n } = useTranslation()
  if (!figure) return <Placeholder>{t('landing.accuracy.pending')}</Placeholder>
  const language: Language = i18n.resolvedLanguage === 'de' ? 'de' : 'en'
  const percent = new Intl.NumberFormat(LANGUAGE_LOCALES[language], {
    style: 'percent',
    maximumFractionDigits: 1,
  })
  return <>{percent.format(figure.value)}</>
}
