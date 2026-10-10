import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { buttonVariants } from '@/components/button-variants'
import { EvidenceTag } from '@/components/EvidenceTag'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import { useMotionMoment } from '@/hooks/use-motion-moment'
import { cn } from '@/lib/utils'

/** How long the hero's load sequence keeps its classes: the verdict's focus ends at 3.5 s. */
export const HERO_SEQUENCE_MS = 3600

type CheckKey = 'scope' | 'prohibited' | 'high_risk' | 'transparency'
// The Act's order; the cascade steps in 20 px a pane (the canvas note) from 640 px up.
const CHECKS: readonly { key: CheckKey; indent: string }[] = [
  { key: 'scope', indent: 'sm:ml-5' },
  { key: 'prohibited', indent: 'sm:ml-10' },
  { key: 'high_risk', indent: 'sm:ml-15' },
  { key: 'transparency', indent: 'sm:ml-20' },
]

function CheckMark({ isDeciding }: { isDeciding: boolean }): JSX.Element {
  return (
    <span
      className={cn(
        'intro-mark flex size-[26px] shrink-0 items-center justify-center rounded-full',
        isDeciding ? 'bg-risk-high-tint text-risk-high' : 'bg-risk-minimal-tint text-risk-minimal',
      )}
    >
      <Icon name={isDeciding ? 'alert' : 'check'} size={14} />
    </span>
  )
}

/** One check of the worked example: passed, or (High-risk) the one that decided the class. */
function CheckPane({ check, step }: { check: (typeof CHECKS)[number]; step: number }): JSX.Element {
  const { t } = useTranslation()
  const isDeciding = check.key === 'high_risk'
  const base = `landing.hero.checks.${check.key}` as const
  return (
    <GlassPanel
      as="li"
      glint
      padded={false}
      data-intro-step={`check-${step}`}
      data-deciding={isDeciding ? 'true' : undefined}
      className={cn('flex flex-col gap-2.5 rounded-[20px] px-5 py-4', check.indent)}
    >
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1">
        <CheckMark isDeciding={isDeciding} />
        <span className="w-[140px] text-body-small font-semibold">{t(`${base}.name`)}</span>
        <span className="sr-only">
          {isDeciding ? t('landing.hero.decided') : t('landing.hero.passed')}
        </span>
        <span
          className={cn(
            'min-w-0 flex-1 basis-48 text-body-small',
            isDeciding ? 'font-medium' : 'text-slate',
          )}
        >
          {t(`${base}.finding`)}
        </span>
        <span className="text-caption font-normal whitespace-nowrap text-slate">
          {t(`${base}.cite`)}
        </span>
      </div>
      {isDeciding && (
        <>
          <p className="m-0 pl-10 font-serif text-quote-small text-ink-2">
            {t('landing.hero.checks.high_risk.quote')}
          </p>
          <div className="pl-10">
            <EvidenceTag kind="stated">{t('landing.hero.checks.high_risk.evidence')}</EvidenceTag>
          </div>
        </>
      )}
    </GlassPanel>
  )
}

/** The hero's aside (components.md › CheckCascade): a description, the four checks, the result. */
function CheckCascade(): JSX.Element {
  const { t } = useTranslation()
  return (
    <figure
      aria-label={t('landing.hero.exampleLabel')}
      className="m-0 flex min-w-0 flex-1 flex-col gap-3"
    >
      <GlassPanel
        glint
        padded={false}
        data-intro-step="description"
        className="mb-3 flex flex-col gap-2.5 px-6 py-5.5"
      >
        <p className="text-caption text-slate">{t('landing.hero.descriptionLabel')}</p>
        <p className="text-[17px] leading-normal">{t('landing.hero.description')}</p>
      </GlassPanel>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {CHECKS.map((check, index) => (
          <CheckPane key={check.key} check={check} step={index + 1} />
        ))}
      </ol>
      <GlassPanel
        glint
        padded={false}
        data-intro-step="result"
        className="mt-3 flex flex-wrap items-center justify-between gap-x-7 gap-y-3 rounded-[26px] bg-[linear-gradient(150deg,rgb(255_255_255/0.82),rgb(255_236_220/0.55))] px-6 py-5.5 sm:ml-25"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <p className="flex items-center gap-2.5">
            <span aria-hidden="true" className="size-3 shrink-0 rounded-full bg-risk-high-dot" />
            <span data-intro-step="verdict" className="font-brand text-verdict-small">
              {t('pill.high_risk')}
            </span>
          </p>
          <p className="text-body-small text-slate">{t('landing.hero.role')}</p>
        </div>
        <Link to="/app" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
          {t('landing.hero.todo')}
        </Link>
      </GlassPanel>
    </figure>
  )
}

/**
 * The landing page's opening (components.md › Hero): the dated badge, the visitor's question, the
 * lead, two actions and the note, beside the worked example. On load it resolves in 2.6 s
 * (site-motion.css › the hero sequence); with reduced motion it simply shows.
 */
export function Hero(): JSX.Element {
  const { t } = useTranslation()
  const isIntro = useMotionMoment(HERO_SEQUENCE_MS)
  return (
    <section
      id="top"
      aria-labelledby="hero-title"
      data-intro={isIntro ? 'true' : undefined}
      className="flex flex-col gap-10 lg:flex-row lg:items-center lg:gap-14"
    >
      <div className="flex flex-col gap-7 lg:w-[610px] lg:shrink-0">
        <p
          data-intro-step="badge"
          className="flex min-h-[34px] items-center gap-2 self-start rounded-pill px-3.5 py-1.5 text-label glass-thin"
        >
          <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-lens-blue" />
          {t('landing.hero.badge')}
        </p>
        <h1
          id="hero-title"
          data-intro-step="headline"
          className="m-0 text-[44px] leading-[1.04] font-semibold tracking-[-0.04em] text-balance sm:text-[56px] lg:text-display-hero"
        >
          {t('landing.hero.title')}
        </h1>
        <p data-intro-step="lead" className="max-w-[560px] text-body-large text-slate">
          {t('landing.hero.lead')}
        </p>
        <div data-intro-step="actions" className="flex flex-wrap items-center gap-3">
          <Link to="/app" className={cn(buttonVariants({ size: 'lg' }), 'text-white')}>
            {t('site.classify')}
          </Link>
          <a href="#accuracy" className={buttonVariants({ variant: 'ghost', size: 'lg' })}>
            {t('landing.hero.measured')}
          </a>
        </div>
        <p data-intro-step="note" className="text-label font-normal text-slate">
          {t('landing.hero.note')}
        </p>
      </div>
      <CheckCascade />
    </section>
  )
}
