import { createFileRoute } from '@tanstack/react-router'
import { useState, type JSX, type ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { Button } from '@/components/Button'
import { EvidenceTag } from '@/components/EvidenceTag'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import { ICON_NAMES } from '@/components/icon-files'
import { KlarLogo } from '@/components/KlarLogo'
import { LawDate } from '@/components/LawDate'
import { LawNotice } from '@/components/LawNotice'
import { LAW_SCOPE_CLASS, LawSwitch } from '@/components/LawSwitch'
import { Notice } from '@/components/Notice'
import { PhoneLabel } from '@/components/PhoneLabel'
import { EVIDENCE_KINDS, PILL_KINDS, STATUSES } from '@/components/pill-kinds'
import { RiskPill } from '@/components/RiskPill'
import { SegmentedControl } from '@/components/SegmentedControl'
import { StatusPill } from '@/components/StatusPill'
import { LANGUAGE_LOCALES, type Language } from '@/i18n'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/_site/brand')({ component: BrandPage })

// The system's core swatches, rendered from the theme tokens, so the two can be compared.
const SWATCHES = [
  { key: 'mist', hex: '#E6ECF3', className: 'bg-mist shadow-[inset_0_0_0_1px_rgb(15_27_45/0.1)]' },
  { key: 'ink', hex: '#0F1B2D', className: 'bg-ink' },
  { key: 'slate', hex: '#4A5670', className: 'bg-slate' },
  { key: 'lens', hex: '#2D4BE0', className: 'bg-lens-blue' },
] as const

// The Annex III high-risk date in the amended text and in the original 2024 text.
const ANNEX_III_DATE = { amended: new Date(2027, 11, 2), original: new Date(2026, 7, 2) } as const

type View = 'summary' | 'reviewer'

function Section({
  title,
  children,
  className,
}: {
  title: string
  children: ReactNode
  className?: string
}): JSX.Element {
  return (
    <GlassPanel as="section" className={cn('flex flex-col gap-4', className)}>
      <h2 className="text-heading-small">{title}</h2>
      {children}
    </GlassPanel>
  )
}

function VoicesPanel(): JSX.Element {
  const { t } = useTranslation()
  return (
    <GlassPanel as="section" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h2 className="text-heading-small">{t('brand.voices')}</h2>
        <p className="text-caption text-slate">{t('brand.voicesFonts')}</p>
      </div>
      <p className="text-[26px] leading-tight font-semibold tracking-tight">
        {t('brand.productVoice')}
      </p>
      <p className="font-serif text-[22px] leading-snug text-ink-2">{t('brand.actVoice')}</p>
      <div className="flex flex-col gap-1">
        <p className="text-caption text-slate">{t('brand.verdictVoice')}</p>
        <p className="font-brand text-verdict text-ink">{t('brand.verdictSample')}</p>
      </div>
    </GlassPanel>
  )
}

function ComponentsPanel(): JSX.Element {
  const { t } = useTranslation()
  const [view, setView] = useState<View>('summary')
  return (
    <Section title={t('brand.components')}>
      <div className="flex flex-wrap items-center gap-3">
        <Button>{t('brand.primaryAction')}</Button>
        <Button variant="ghost">{t('brand.secondaryAction')}</Button>
        <Button variant="ghost" size="sm" icon="add">
          {t('brand.addAction')}
        </Button>
      </div>
      <SegmentedControl<View>
        label={t('brand.viewLabel')}
        value={view}
        onChange={setView}
        options={[
          { value: 'summary', label: t('brand.summary') },
          { value: 'reviewer', label: t('brand.reviewer') },
        ]}
        className="self-start"
      />
      <Notice />
    </Section>
  )
}

function StatusesPanel(): JSX.Element {
  const { t } = useTranslation()
  return (
    <Section title={t('brand.statuses')}>
      <ul className="flex flex-wrap gap-2">
        {STATUSES.map((status) => (
          <li key={status}>
            <StatusPill status={status} />
          </li>
        ))}
      </ul>
      <ul className="flex flex-wrap gap-2">
        {EVIDENCE_KINDS.map((kind) => (
          <li key={kind}>
            <EvidenceTag kind={kind} />
          </li>
        ))}
      </ul>
      <h3 className="text-label text-slate">{t('brand.icons')}</h3>
      <ul className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        {ICON_NAMES.map((name) => (
          <li key={name} className="flex flex-col items-center gap-1.5 text-ink">
            <Icon name={name} size={22} />
            <code className="font-mono text-micro text-slate">{name}</code>
          </li>
        ))}
      </ul>
    </Section>
  )
}

function LawPanel(): JSX.Element {
  const { t, i18n } = useTranslation()
  const language: Language = i18n.resolvedLanguage === 'de' ? 'de' : 'en'
  const format = new Intl.DateTimeFormat(LANGUAGE_LOCALES[language], { dateStyle: 'long' })
  return (
    <Section title={t('brand.law')} className={LAW_SCOPE_CLASS}>
      <LawSwitch
        className="self-start"
        amendedLabel={<PhoneLabel phone={t('lawShort.amended')} wide={t('law.amended')} />}
        originalLabel={<PhoneLabel phone={t('lawShort.original')} wide={t('law.original')} />}
      />
      <p className="text-body-small">
        <Trans
          i18nKey="brand.lawDateSample"
          components={{
            date: (
              <LawDate
                amended={format.format(ANNEX_III_DATE.amended)}
                original={format.format(ANNEX_III_DATE.original)}
              />
            ),
          }}
        />
      </p>
      <LawNotice />
    </Section>
  )
}

/** A style sheet of the tokens and base components, for checking them against the design system. */
function BrandPage(): JSX.Element {
  const { t } = useTranslation()
  return (
    <div className="mt-6 flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-heading-page">{t('brand.title')}</h1>
        <p className="max-w-prose text-slate">{t('brand.intro')}</p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <GlassPanel className="flex h-48 flex-col justify-between">
          <p className="text-caption text-slate">{t('brand.onLight')}</p>
          <KlarLogo className="h-11 w-auto self-start" />
        </GlassPanel>
        <GlassPanel tone="dark" className="flex h-48 flex-col justify-between">
          <p className="text-caption text-paper/80">{t('brand.onDark')}</p>
          <KlarLogo tone="dark" className="h-11 w-auto self-start" />
        </GlassPanel>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Section title={t('brand.colour')}>
          <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            {SWATCHES.map((swatch) => (
              <li key={swatch.key} className="flex flex-col gap-1.5">
                <span aria-hidden="true" className={`h-13 rounded-item ${swatch.className}`} />
                <span className="text-xs font-semibold">{t(`brand.swatch.${swatch.key}`)}</span>
                <span className="text-xs text-slate">{swatch.hex}</span>
              </li>
            ))}
          </ul>
          <p className="text-caption text-slate">{t('brand.pills')}</p>
          <ul className="flex flex-wrap gap-2">
            {PILL_KINDS.map((kind) => (
              <li key={kind}>
                <RiskPill kind={kind} />
              </li>
            ))}
          </ul>
        </Section>

        <div className="flex flex-col gap-6">
          <VoicesPanel />
          <GlassPanel as="section" className="flex flex-col gap-2 px-7 py-5">
            <h2 className="text-heading-small">{t('brand.glass')}</h2>
            <p className="text-caption leading-relaxed text-slate">{t('brand.glassRecipe')}</p>
          </GlassPanel>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ComponentsPanel />
        <StatusesPanel />
        <LawPanel />
      </div>
    </div>
  )
}
