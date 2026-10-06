import { Link } from '@tanstack/react-router'
import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { buttonVariants } from '@/components/button-variants'
import { GlassPanel } from '@/components/GlassPanel'
import { Icon } from '@/components/Icon'
import { useUserDataOverview } from '@/hooks/use-user-data-overview'

import { ImportDataButton } from './ImportDataButton'

/** "Your AI tools": the empty state while there are none, otherwise how many and a way there. */
export function ToolsPanel(): JSX.Element {
  const { t } = useTranslation()
  const headingId = useId()
  const toolCount = useUserDataOverview().data?.toolCount ?? 0
  return (
    <GlassPanel as="section" aria-labelledby={headingId} className="flex flex-col gap-4 p-6.5">
      <h2 id={headingId} className="m-0 text-heading-small text-ink">
        {t('welcome.tools.heading')}
      </h2>
      {toolCount > 0 ? (
        <div className="flex flex-col items-start gap-3">
          <p className="m-0 text-body text-ink">{t('welcome.tools.count', { count: toolCount })}</p>
          <Link to="/app/inventory" className={buttonVariants({ variant: 'ghost' })}>
            {t('welcome.tools.open')}
          </Link>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2.5 rounded-[18px] border-[1.5px] border-dashed border-border px-5 py-6.5 text-center">
          <span className="flex size-11 items-center justify-center rounded-item bg-lens-blue-soft text-lens-blue">
            <Icon name="inventory" />
          </span>
          <p className="m-0 text-body font-semibold text-ink">{t('welcome.tools.emptyTitle')}</p>
          <p className="m-0 text-body-small text-slate">{t('welcome.tools.emptyBody')}</p>
          <Link to="/app/classify" className={buttonVariants({ className: 'mt-1.5' })}>
            {t('welcome.tools.classifyFirst')}
          </Link>
        </div>
      )}
      {/* Outside the two states, so the import's outcome stays on screen when the tools arrive. */}
      <ImportDataButton />
    </GlassPanel>
  )
}
