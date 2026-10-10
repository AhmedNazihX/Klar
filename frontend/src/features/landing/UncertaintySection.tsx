import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import { Reveal } from '@/components/Reveal'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'

import { STAGGER_MS } from './ChecksSection'
import { SectionTitle } from './SectionTitle'

const ANSWERS = ['yes', 'no', 'notSure'] as const

function AnswerChip({ children }: { children: string }): JSX.Element {
  return (
    <span className="inline-flex h-[26px] items-center rounded-pill bg-white px-2.5 text-[13px] font-semibold shadow-[inset_0_0_0_1px_rgb(15_27_45/0.15)]">
      {children}
    </span>
  )
}

/**
 * "When it isn't sure, it says so." (components.md › UncertaintyCard): Needs more information with
 * the question Klar asks, and Legally ambiguous with both readings and the stricter one kept.
 */
export function UncertaintySection(): JSX.Element {
  const { t } = useTranslation()
  return (
    <section
      aria-labelledby="unsure"
      className="mt-32 flex flex-col gap-10 lg:flex-row lg:items-stretch lg:gap-12"
    >
      <div className="flex flex-col gap-4.5 pt-3 lg:w-[420px] lg:shrink-0">
        <SectionTitle id="unsure">{t('landing.unsure.title')}</SectionTitle>
        <p className="text-[17px] leading-normal text-slate">{t('landing.unsure.lead')}</p>
      </div>
      <div className="grid flex-1 grid-cols-1 gap-5 md:grid-cols-2">
        <Reveal className="flex">
          <GlassPanel glint padded={false} className="flex w-full flex-col gap-4 p-7.5">
            <StatusPill status="needs-info" className="self-start" />
            <p className="text-heading-small font-medium">{t('landing.unsure.info.summary')}</p>
            <GlassPanel
              tone="thin"
              padded={false}
              className="flex flex-col gap-3 rounded-[18px] px-4.5 py-4"
            >
              <p className="text-body-small font-semibold">{t('landing.unsure.info.question')}</p>
              <div className="flex flex-wrap gap-2">
                {ANSWERS.map((answer) => (
                  <AnswerChip key={answer}>{t(`landing.unsure.info.${answer}`)}</AnswerChip>
                ))}
              </div>
            </GlassPanel>
            <p className="text-label font-normal text-slate">{t('landing.unsure.info.next')}</p>
          </GlassPanel>
        </Reveal>
        <Reveal delay={STAGGER_MS} className="flex">
          <GlassPanel glint padded={false} className="flex w-full flex-col gap-4 p-7.5">
            <StatusPill status="ambiguous" className="self-start" />
            <p className="text-heading-small font-medium">
              {t('landing.unsure.ambiguous.summary')}
            </p>
            <GlassPanel
              tone="thin"
              padded={false}
              className="flex flex-col gap-2.5 rounded-[18px] px-4.5 py-4"
            >
              <p className="flex flex-wrap items-center justify-between gap-3 text-body-small">
                <span>{t('landing.unsure.ambiguous.narrow')}</span>
                <RiskPill kind="limited_risk" label={t('landing.unsure.ambiguous.notHighRisk')} />
              </p>
              <p className="flex flex-wrap items-center justify-between gap-3 text-body-small">
                <span className="font-semibold">{t('landing.unsure.ambiguous.recruitment')}</span>
                <RiskPill kind="high_risk" />
              </p>
            </GlassPanel>
            <p className="text-label font-normal text-slate">
              {t('landing.unsure.ambiguous.next')}
            </p>
          </GlassPanel>
        </Reveal>
      </div>
    </section>
  )
}
