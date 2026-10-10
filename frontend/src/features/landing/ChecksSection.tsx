import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { EvidenceTag } from '@/components/EvidenceTag'
import { GlassPanel } from '@/components/GlassPanel'
import { EVIDENCE_KINDS } from '@/components/pill-kinds'
import { Reveal } from '@/components/Reveal'

import { SectionTitle } from './SectionTitle'

/** The stagger token: the four checks arrive 1, 2, 3, 4, then the role line. */
export const STAGGER_MS = 110

const CHECKS = ['scope', 'prohibited', 'high_risk', 'transparency'] as const

/**
 * "It checks in the Act's order, and shows its work." (components.md › CheckCard): the four checks
 * in their legal order, then the role step and the three evidence tags.
 */
export function ChecksSection(): JSX.Element {
  const { t } = useTranslation()
  return (
    <section
      id="how"
      aria-labelledby="how-title"
      className="mt-32 flex scroll-mt-28 flex-col gap-10"
    >
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end md:gap-10">
        <SectionTitle id="how-title" className="max-w-[640px]">
          {t('landing.how.title')}
        </SectionTitle>
        <p className="max-w-[480px] text-[17px] leading-normal text-slate">
          {t('landing.how.lead')}
        </p>
      </div>
      <ol className="m-0 grid list-none grid-cols-1 gap-5 p-0 sm:grid-cols-2 lg:grid-cols-4">
        {CHECKS.map((check, index) => (
          <Reveal as="li" key={check} delay={index * STAGGER_MS} className="flex">
            <GlassPanel glint className="flex min-h-[260px] w-full flex-col gap-3.5">
              <span
                aria-hidden="true"
                className="text-[44px] leading-none font-light tracking-[-0.04em] text-lens-blue"
              >
                {index + 1}
              </span>
              <h3 className="m-0 text-[21px] leading-tight font-semibold tracking-[-0.01em]">
                {t(`landing.how.checks.${check}.name`)}
              </h3>
              <p className="text-body-small text-slate">
                {t(`landing.how.checks.${check}.question`)}
              </p>
              <p className="mt-auto text-caption font-semibold">
                {t(`landing.how.checks.${check}.cite`)}
              </p>
            </GlassPanel>
          </Reveal>
        ))}
      </ol>
      <Reveal delay={CHECKS.length * STAGGER_MS}>
        <GlassPanel
          tone="thin"
          radius="tile"
          padded={false}
          className="flex flex-col gap-5 px-7 py-5.5 md:flex-row md:items-center md:gap-8"
        >
          <p className="text-body font-medium md:w-[360px] md:shrink-0">{t('landing.how.role')}</p>
          <div aria-hidden="true" className="hidden w-px self-stretch bg-ink/12 md:block" />
          <div className="flex flex-col gap-2.5">
            <p className="text-body-small text-slate">{t('landing.how.evidenceLead')}</p>
            <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-2 p-0">
              {EVIDENCE_KINDS.map((kind) => (
                <li key={kind} className="flex items-baseline gap-2 text-body-small">
                  <EvidenceTag kind={kind} />
                  {t(`landing.how.evidence.${kind}`)}
                </li>
              ))}
            </ul>
          </div>
        </GlassPanel>
      </Reveal>
    </section>
  )
}
