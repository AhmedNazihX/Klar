import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'

/** A holding page at `/` and `/de` until the landing page (story P16, `Main` and `MainDE`). */
export function HoldingPage(): JSX.Element {
  const { t } = useTranslation()
  return (
    <GlassPanel radius="feature" className="flex max-w-3xl flex-col gap-4 p-8 sm:p-12">
      <p className="m-0 text-label text-slate">{t('app.tagline')}</p>
      <h1 className="m-0 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {t('home.title')}
      </h1>
      <p className="m-0 max-w-prose text-lg leading-relaxed text-slate">{t('home.body')}</p>
    </GlassPanel>
  )
}
