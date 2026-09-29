import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import { KlarLogo } from '@/components/KlarLogo'
import { PILL_KINDS } from '@/components/pill-kinds'
import { RiskPill } from '@/components/RiskPill'

export const Route = createFileRoute('/brand')({ component: BrandPage })

// The Brand board's swatches, rendered from the theme tokens, so the two can be compared.
const SWATCHES = [
  { key: 'mist', hex: '#E6ECF3', className: 'bg-mist shadow-[inset_0_0_0_1px_rgb(15_27_45/0.1)]' },
  { key: 'ink', hex: '#0F1B2D', className: 'bg-ink' },
  { key: 'slate', hex: '#4A5670', className: 'bg-slate' },
  { key: 'lens', hex: '#2D4BE0', className: 'bg-lens' },
] as const

/** A style sheet of the tokens, for checking them against the Brand board. */
function BrandPage(): JSX.Element {
  const { t } = useTranslation()
  return (
    <div className="mt-6 flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">{t('brand.title')}</h1>
        <p className="max-w-prose text-muted-foreground">{t('brand.intro')}</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <GlassPanel className="flex h-48 flex-col justify-between p-7">
          <p className="text-[13px] font-medium text-muted-foreground">{t('brand.onLight')}</p>
          <KlarLogo className="h-11 w-auto self-start" />
        </GlassPanel>
        <GlassPanel tone="dark" className="flex h-48 flex-col justify-between p-7">
          <p className="text-[13px] font-medium text-white/75">{t('brand.onDark')}</p>
          <KlarLogo tone="dark" className="h-11 w-auto self-start" />
        </GlassPanel>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <GlassPanel className="flex flex-col gap-4 p-7">
          <h2 className="text-base font-semibold">{t('brand.colour')}</h2>
          <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            {SWATCHES.map((swatch) => (
              <li key={swatch.key} className="flex flex-col gap-1.5">
                <span aria-hidden="true" className={`h-13 rounded-[14px] ${swatch.className}`} />
                <span className="text-xs font-semibold">{t(`brand.swatch.${swatch.key}`)}</span>
                <span className="text-xs text-muted-foreground">{swatch.hex}</span>
              </li>
            ))}
          </ul>
          <p className="text-[13px] text-muted-foreground">{t('brand.pills')}</p>
          <ul className="flex flex-wrap gap-2">
            {PILL_KINDS.map((kind) => (
              <li key={kind}>
                <RiskPill kind={kind} />
              </li>
            ))}
          </ul>
        </GlassPanel>

        <div className="flex flex-col gap-6">
          <GlassPanel className="flex flex-col gap-3 p-7">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="text-base font-semibold">{t('brand.voices')}</h2>
              <p className="text-[13px] text-muted-foreground">{t('brand.voicesFonts')}</p>
            </div>
            <p className="text-[26px] leading-tight font-semibold tracking-tight">
              {t('brand.productVoice')}
            </p>
            <p className="font-serif text-[22px] leading-snug text-ink-soft">
              {t('brand.actVoice')}
            </p>
          </GlassPanel>
          <GlassPanel className="flex flex-col gap-2 px-7 py-5">
            <h2 className="text-base font-semibold">{t('brand.glass')}</h2>
            <p className="text-[13px] leading-relaxed text-muted-foreground">
              {t('brand.glassRecipe')}
            </p>
          </GlassPanel>
        </div>
      </div>
    </div>
  )
}
