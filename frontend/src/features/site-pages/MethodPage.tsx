import type { JSX, ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'

import { AccuracyFigure } from '@/components/AccuracyFigure'
import { GlassPanel } from '@/components/GlassPanel'
import { Placeholder } from '@/components/Placeholder'
import { PLACEHOLDER_TAGS } from '@/components/placeholder-tags'
import { SITE_ACCURACY, type SiteAccuracy } from '@/lib/accuracy'

import { InfoRows, InfoSection, InfoText, PageIntro, type InfoRow } from './SitePageParts'

function MetricTile({
  value,
  label,
  detail,
}: {
  value: ReactNode
  label: string
  detail: ReactNode
}): JSX.Element {
  return (
    <GlassPanel
      as="li"
      tone="thin"
      padded={false}
      className="flex flex-col gap-2 rounded-[22px] p-5.5"
    >
      <p className="m-0 flex min-h-11 flex-wrap items-center gap-2 text-[36px] leading-[44px] font-semibold tracking-[-0.03em]">
        {value}
      </p>
      <p className="m-0 text-body font-semibold">{label}</p>
      <p className="m-0 text-label leading-[1.55] font-normal text-slate">{detail}</p>
    </GlassPanel>
  )
}

/** The four figures, read from the same accuracy.json as the landing page (P16, P27). */
function CountSection({ accuracy }: { accuracy: SiteAccuracy }): JSX.Element {
  const { t } = useTranslation()
  const headToHead = accuracy.head_to_head
  return (
    <InfoSection title={t('sitePages.method.count.title')}>
      <ul className="m-0 grid list-none grid-cols-1 gap-4 p-0 md:grid-cols-2">
        <MetricTile
          value={<AccuracyFigure figure={accuracy.risk_class_accuracy} />}
          label={t('landing.accuracy.riskClass.label')}
          detail={t('sitePages.method.count.riskClass')}
        />
        <MetricTile
          value={<AccuracyFigure figure={accuracy.false_low_risk_rate} />}
          label={t('landing.accuracy.falseLow.label')}
          detail={t('sitePages.method.count.falseLow')}
        />
        <MetricTile
          value={<AccuracyFigure figure={accuracy.citations_exist} />}
          label={t('landing.accuracy.citations.label')}
          detail={t('sitePages.method.count.citations')}
        />
        <MetricTile
          value={
            <>
              <AccuracyFigure figure={headToHead?.klar ?? null} />
              <span className="text-heading-small font-medium text-slate">
                {t('landing.accuracy.checker.versus')}
              </span>
              <AccuracyFigure figure={headToHead?.checker ?? null} />
            </>
          }
          label={t('landing.accuracy.checker.label')}
          detail={
            headToHead ? (
              t('sitePages.method.count.checker', {
                cases: headToHead.cases,
                name: headToHead.checker_name,
              })
            ) : (
              <Trans
                i18nKey="sitePages.method.count.checkerPending"
                components={PLACEHOLDER_TAGS}
              />
            )
          }
        />
      </ul>
    </InfoSection>
  )
}

const SCORE_STEPS = ['run', 'compare', 'citations', 'uncertainty'] as const

function ScoreSection(): JSX.Element {
  const { t } = useTranslation()
  const rows: InfoRow[] = SCORE_STEPS.map((step, index) => ({
    key: step,
    label: (
      <>
        <span className="mr-3 tabular-nums">{index + 1}</span>
        {t(`sitePages.method.score.${step}`)}
      </>
    ),
    text: t(`sitePages.method.score.${step}Text`),
  }))
  return (
    <InfoSection title={t('sitePages.method.score.title')}>
      <InfoRows rows={rows} />
    </InfoSection>
  )
}

function LimitsSection(): JSX.Element {
  const { t } = useTranslation()
  const rows: InfoRow[] = [
    {
      key: 'size',
      label: t('sitePages.method.limits.size'),
      text: <Trans i18nKey="sitePages.method.limits.sizeText" components={PLACEHOLDER_TAGS} />,
    },
    {
      key: 'labels',
      label: t('sitePages.method.limits.labels'),
      text: <Trans i18nKey="sitePages.method.limits.labelsText" components={PLACEHOLDER_TAGS} />,
    },
    {
      key: 'guidance',
      label: t('sitePages.method.limits.guidance'),
      text: t('sitePages.method.limits.guidanceText'),
    },
    {
      key: 'descriptions',
      label: t('sitePages.method.limits.descriptions'),
      text: t('sitePages.method.limits.descriptionsText'),
    },
    {
      key: 'penalties',
      label: t('sitePages.method.limits.penalties'),
      text: t('sitePages.method.limits.penaltiesText'),
    },
  ]
  return (
    <InfoSection title={t('sitePages.method.limits.title')}>
      <InfoRows rows={rows} />
    </InfoSection>
  )
}

function ResultsSection(): JSX.Element {
  const { t } = useTranslation()
  const rows: InfoRow[] = [
    {
      key: 'lastRun',
      label: t('sitePages.method.results.lastRun'),
      text: <Placeholder>{t('sitePages.method.results.lastRunPh')}</Placeholder>,
    },
    {
      key: 'lawVersion',
      label: t('sitePages.method.results.lawVersion'),
      text: t('sitePages.method.results.lawVersionText'),
    },
    {
      key: 'report',
      label: t('sitePages.method.results.report'),
      text: <Placeholder>{t('sitePages.method.results.reportPh')}</Placeholder>,
    },
  ]
  return (
    <InfoSection title={t('sitePages.method.results.title')}>
      <InfoRows rows={rows} />
    </InfoSection>
  )
}

/**
 * How Klar is measured (artboard `Method`, INIT › Evaluation): the test set, the four figures,
 * how a case is scored, the method's limits (national penalty rules out of scope, decision 026
 * item 1) and the run the figures come from. Every unknown is a marked placeholder.
 */
export function MethodPage({ accuracy = SITE_ACCURACY }: { accuracy?: SiteAccuracy }): JSX.Element {
  const { t } = useTranslation()
  return (
    <>
      <PageIntro title={t('site.page.method')} lead={t('sitePages.method.lead')} />
      <InfoSection title={t('sitePages.method.set.title')}>
        <InfoText>
          <Trans i18nKey="sitePages.method.set.text" components={PLACEHOLDER_TAGS} />
        </InfoText>
      </InfoSection>
      <CountSection accuracy={accuracy} />
      <ScoreSection />
      <LimitsSection />
      <ResultsSection />
    </>
  )
}
