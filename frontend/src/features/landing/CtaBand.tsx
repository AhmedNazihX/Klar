import { Link } from '@tanstack/react-router'
import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { buttonVariants } from '@/components/button-variants'
import { Reveal } from '@/components/Reveal'
import { cn } from '@/lib/utils'

import { SectionTitle } from './SectionTitle'

/**
 * The closing invitation (components.md › CtaBand): one low-pressure sentence, one line on the
 * effort, and the nav's own action. The only glass panel with a cool blue tint.
 */
export function CtaBand(): JSX.Element {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="cta-title" className="mt-32">
      <Reveal className="flex flex-col items-start justify-between gap-8 rounded-[40px] bg-[linear-gradient(150deg,rgb(255_255_255/0.78),rgb(220_228_255/0.5))] p-8 glass md:flex-row md:items-center md:p-14">
        <div className="flex flex-col gap-3">
          <SectionTitle id="cta-title" size="medium">
            {t('landing.cta.title')}
          </SectionTitle>
          <p className="text-[17px] leading-normal text-slate">{t('landing.cta.lead')}</p>
        </div>
        <Link to="/app" className={cn(buttonVariants({ size: 'lg' }), 'text-white')}>
          {t('site.classify')}
        </Link>
      </Reveal>
    </section>
  )
}
