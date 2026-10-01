import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from './GlassPanel'

/**
 * An empty screen in its frame: the page heading and one glass panel saying the screen is still
 * being built. Each screen's own story replaces it.
 */
export function ScreenPlaceholder({ title }: { title: string }): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <h1 className="m-0 text-[30px] leading-tight font-semibold tracking-[-0.03em] text-ink md:text-heading-page">
        {title}
      </h1>
      <GlassPanel>
        <p className="m-0 text-body text-slate">{t('screen.placeholder')}</p>
      </GlassPanel>
    </>
  )
}
