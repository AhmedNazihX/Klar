import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import { landingPathFor } from '@/components/site-paths'

/** The router's error and not-found page. It never shows the error's text, which may hold data. */
export function ErrorView({ isNotFound = false }: { isNotFound?: boolean }): JSX.Element {
  const { t, i18n } = useTranslation()
  return (
    <GlassPanel role="alert" className="mx-auto mt-12 flex max-w-xl flex-col gap-3 p-8">
      <h1 className="text-xl font-semibold">{t('error.title')}</h1>
      <p className="text-muted-foreground">{isNotFound ? t('error.notFound') : t('error.body')}</p>
      <Link
        to={landingPathFor(i18n.resolvedLanguage)}
        className="font-medium text-lens-blue underline-offset-4 hover:text-lens-blue-hover hover:underline"
      >
        {t('error.home')}
      </Link>
    </GlassPanel>
  )
}
