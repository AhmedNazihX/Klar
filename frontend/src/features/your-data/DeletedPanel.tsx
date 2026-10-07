import { Link } from '@tanstack/react-router'
import { useEffect, useId, useRef, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'

/**
 * Where a deletion ends: the data is gone and the session has ended. Start again opens Welcome,
 * which starts a new anonymous session. The heading takes focus, as the dialog that had it is gone.
 */
export function DeletedPanel(): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => headingRef.current?.focus(), [])
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex max-w-[760px] flex-col items-start gap-3.5 p-10"
    >
      <span className="flex size-12 items-center justify-center rounded-full bg-risk-minimal-tint text-risk-minimal">
        <Icon name="check" />
      </span>
      <h2
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        className="m-0 text-2xl font-semibold tracking-[-0.02em] text-ink outline-none"
      >
        {t('yourData.deleted.title')}
      </h2>
      <p className="m-0 text-body-small text-slate">{t('yourData.deleted.body')}</p>
      <Link to="/app/welcome" className={buttonVariants({ className: 'mt-1.5' })}>
        {t('yourData.deleted.startAgain')}
      </Link>
    </GlassPanel>
  )
}
