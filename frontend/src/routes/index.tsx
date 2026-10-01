import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'

export const Route = createFileRoute('/')({ component: HomePage })

// A holding page until the landing page (story P5, `Main` artboard).
function HomePage(): JSX.Element {
  const { t } = useTranslation()
  return (
    <GlassPanel radius="feature" className="mt-8 flex max-w-3xl flex-col gap-4 p-8 sm:p-12">
      <p className="text-sm font-medium text-muted-foreground">{t('app.tagline')}</p>
      <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {t('home.title')}
      </h1>
      <p className="max-w-prose text-lg leading-relaxed text-muted-foreground">{t('home.body')}</p>
    </GlassPanel>
  )
}
