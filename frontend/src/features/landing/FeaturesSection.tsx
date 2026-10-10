import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import type { PillKind } from '@/components/pill-kinds'
import { Reveal } from '@/components/Reveal'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'

import { SectionTitle } from './SectionTitle'

// The artboard staggers the three cards 120 ms apart.
const FEATURE_STAGGER_MS = 120

const TOOLS: readonly { key: 'screening' | 'chat' | 'routes'; kind: PillKind }[] = [
  { key: 'screening', kind: 'high_risk' },
  { key: 'chat', kind: 'limited_risk' },
  { key: 'routes', kind: 'minimal_risk' },
]

const DUTIES = ['oversight', 'logs', 'inform'] as const

function Preview({ children }: { children: ReactNode }): JSX.Element {
  return (
    <GlassPanel
      tone="thin"
      padded={false}
      className="flex min-h-32 flex-col gap-2.5 rounded-[18px] px-4 py-3.5 text-label"
    >
      {children}
    </GlassPanel>
  )
}

function FeatureCard({
  title,
  body,
  delay,
  preview,
}: {
  title: string
  body: string
  delay: number
  preview: ReactNode
}): JSX.Element {
  return (
    <Reveal as="li" delay={delay} className="flex">
      <GlassPanel glint className="flex w-full flex-col gap-4.5">
        {preview}
        <h3 className="m-0 text-[21px] leading-tight font-semibold">{title}</h3>
        <p className="text-body-small text-slate">{body}</p>
      </GlassPanel>
    </Reveal>
  )
}

/**
 * "From one tool to your whole list." (components.md › FeatureCard): the inventory, the duties
 * checklist and the drafted documents, each with a small preview made of real components.
 */
export function FeaturesSection(): JSX.Element {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="features" className="mt-32 flex flex-col gap-9">
      <SectionTitle id="features">{t('landing.features.title')}</SectionTitle>
      <ul className="m-0 grid list-none grid-cols-1 gap-5 p-0 md:grid-cols-3">
        <FeatureCard
          title={t('landing.features.inventory.title')}
          body={t('landing.features.inventory.body')}
          delay={0}
          preview={
            <Preview>
              {TOOLS.map(({ key, kind }) => (
                <p key={key} className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{t(`landing.features.inventory.${key}`)}</span>
                  <RiskPill kind={kind} />
                </p>
              ))}
            </Preview>
          }
        />
        <FeatureCard
          title={t('landing.features.checklist.title')}
          body={t('landing.features.checklist.body')}
          delay={FEATURE_STAGGER_MS}
          preview={
            <Preview>
              {DUTIES.map((key) => (
                <p key={key} className="flex items-center gap-2.5">
                  <span
                    aria-hidden="true"
                    className="size-4.5 shrink-0 rounded-md shadow-[inset_0_0_0_1.5px_var(--color-slate)]"
                  />
                  <span className="flex-1 font-medium">
                    {t(`landing.features.checklist.${key}`)}
                  </span>
                  <span className="whitespace-nowrap text-slate">
                    {t(`landing.features.checklist.${key}Cite`)}
                  </span>
                </p>
              ))}
            </Preview>
          }
        />
        <FeatureCard
          title={t('landing.features.drafts.title')}
          body={t('landing.features.drafts.body')}
          delay={2 * FEATURE_STAGGER_MS}
          preview={
            <div className="relative flex min-h-32 flex-col gap-2 rounded-[18px] bg-white/85 px-4 py-3.5 shadow-[inset_0_0_0_1px_rgb(15_27_45/0.08)]">
              <StatusPill status="draft" className="absolute top-3 right-3.5" />
              <p className="max-w-[220px] pr-16 text-label font-semibold">
                {t('landing.features.drafts.document')}
              </p>
              <span aria-hidden="true" className="h-1.5 w-[90%] rounded-sm bg-ink/12" />
              <span aria-hidden="true" className="h-1.5 w-[76%] rounded-sm bg-ink/12" />
              <p className="text-caption text-lens-blue">{t('landing.features.drafts.fill')}</p>
            </div>
          }
        />
      </ul>
    </section>
  )
}
