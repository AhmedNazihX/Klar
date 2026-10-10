import { Link } from '@tanstack/react-router'
import type { JSX, ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import { Reveal } from '@/components/Reveal'
import { LANGUAGE_LOCALES, type Language } from '@/i18n'
import { SITE_ACCURACY, type AccuracyFigure, type SiteAccuracy } from '@/lib/accuracy'

import { SectionTitle } from './SectionTitle'

// The artboard brings the four tiles in from 200 ms, 100 ms apart, after the panel.
const TILE_DELAYS_MS = [200, 300, 400, 500] as const

/** A value nobody has measured yet, marked so it can't pass for a real one (`.kl-ph`). */
function Placeholder({ children }: { children?: ReactNode }): JSX.Element {
  return (
    <span data-placeholder="true" className="rounded-[6px] bg-lens-blue/8 px-1.5 text-lens-blue">
      {children}
    </span>
  )
}

function Tile({
  delay,
  value,
  label,
  detail,
}: {
  delay: number
  value: ReactNode
  label: string
  detail: ReactNode
}): JSX.Element {
  return (
    <Reveal as="li" delay={delay} className="flex">
      <GlassPanel
        tone="thin"
        glint
        padded={false}
        className="flex w-full flex-col gap-1.5 rounded-[22px] p-5.5"
      >
        <p className="flex h-12 items-center gap-2 text-[40px] leading-[48px] font-semibold tracking-[-0.03em] whitespace-nowrap">
          {value}
        </p>
        <p className="text-body-small font-semibold">{label}</p>
        <p className="text-label font-normal text-slate">{detail}</p>
      </GlassPanel>
    </Reveal>
  )
}

/**
 * "Accuracy is measured and published, not promised." (components.md › MetricTile): four figures
 * read from src/content/accuracy.json, each a marked `[—%]` until P27 publishes the measured value.
 */
export function AccuracySection({
  accuracy = SITE_ACCURACY,
}: {
  accuracy?: SiteAccuracy
}): JSX.Element {
  const { t, i18n } = useTranslation()
  const language: Language = i18n.resolvedLanguage === 'de' ? 'de' : 'en'
  const percent = new Intl.NumberFormat(LANGUAGE_LOCALES[language], {
    style: 'percent',
    maximumFractionDigits: 1,
  })
  const pending = t('landing.accuracy.pending')
  const show = (figure: AccuracyFigure | null): ReactNode =>
    figure ? percent.format(figure.value) : <Placeholder>{pending}</Placeholder>
  const headToHead = accuracy.head_to_head

  return (
    <section id="accuracy" aria-labelledby="accuracy-title" className="mt-32 scroll-mt-28">
      <Reveal className="flex flex-col gap-10 rounded-feature p-7 glass md:p-12 lg:flex-row lg:gap-14">
        <div className="flex flex-col gap-4.5 lg:w-[460px] lg:shrink-0">
          <SectionTitle id="accuracy-title" size="medium">
            {t('landing.accuracy.title')}
          </SectionTitle>
          <p className="text-body leading-[1.6] text-slate">{t('landing.accuracy.lead')}</p>
          <Link to="/method" className="self-start text-body font-medium text-lens-blue">
            {t('landing.accuracy.method')}
          </Link>
        </div>
        <ul className="m-0 grid flex-1 list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2">
          <Tile
            delay={TILE_DELAYS_MS[0]}
            value={show(accuracy.risk_class_accuracy)}
            label={t('landing.accuracy.riskClass.label')}
            detail={t('landing.accuracy.riskClass.detail')}
          />
          <Tile
            delay={TILE_DELAYS_MS[1]}
            value={show(accuracy.false_low_risk_rate)}
            label={t('landing.accuracy.falseLow.label')}
            detail={t('landing.accuracy.falseLow.detail')}
          />
          <Tile
            delay={TILE_DELAYS_MS[2]}
            value={show(accuracy.citations_exist)}
            label={t('landing.accuracy.citations.label')}
            detail={t('landing.accuracy.citations.detail')}
          />
          <Tile
            delay={TILE_DELAYS_MS[3]}
            value={
              <span className="flex items-center gap-2 text-[30px]">
                {show(headToHead?.klar ?? null)}
                <span className="text-heading-small font-medium text-slate">
                  {t('landing.accuracy.checker.versus')}
                </span>
                {show(headToHead?.checker ?? null)}
              </span>
            }
            label={t('landing.accuracy.checker.label')}
            detail={
              headToHead ? (
                t('landing.accuracy.checker.detail', {
                  cases: headToHead.cases,
                  name: headToHead.checker_name,
                })
              ) : (
                <Trans
                  i18nKey="landing.accuracy.checker.detailPending"
                  components={{ cases: <Placeholder />, name: <Placeholder /> }}
                />
              )
            }
          />
        </ul>
      </Reveal>
    </section>
  )
}
