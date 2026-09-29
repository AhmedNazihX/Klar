import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'

/** The router's error and not-found page. It never shows the error's text, which may hold data. */
export function ErrorView({ isNotFound = false }: { isNotFound?: boolean }): JSX.Element {
  const { t } = useTranslation()
  return (
    <GlassPanel role="alert" className="mx-auto mt-12 flex max-w-xl flex-col gap-3 p-8">
      <h1 className="text-xl font-semibold">{t('error.title')}</h1>
      <p className="text-muted-foreground">{isNotFound ? t('error.notFound') : t('error.body')}</p>
      <Link to="/" className="font-medium text-lens underline-offset-4 hover:underline">
        {t('error.home')}
      </Link>
    </GlassPanel>
  )
}
