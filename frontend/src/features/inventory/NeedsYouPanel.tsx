import { Link } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { useId, type JSX } from 'react'
import { useTranslation } from 'react-i18next'

import { GlassPanel } from '@/components/GlassPanel'
import { RiskPill } from '@/components/RiskPill'
import { StatusPill } from '@/components/StatusPill'
import { provisionName } from '@/features/classify/provision-names'
import { useLanguage } from '@/hooks/use-language'
import type { Language } from '@/i18n'

import type { NeedsYou } from './company-summary'

function action(t: TFunction, need: NeedsYou, language: Language): string {
  switch (need.kind) {
    case 'prohibited':
      return t('inventory.needs.prohibited')
    case 'needs-info':
      return t('inventory.needs.needsInfo', { count: need.questions })
    case 'ambiguous':
      return need.provision
        ? t('inventory.needs.ambiguous', { provision: provisionName(need.provision, language) })
        : t('inventory.needs.ambiguousPlain')
  }
}

function NeedPill({ need }: { need: NeedsYou }): JSX.Element {
  if (need.kind === 'prohibited') return <RiskPill kind="prohibited" />
  return <StatusPill status={need.kind} size="sm" />
}

/** "N tools need you": each prohibited, paused or ambiguous tool with what to do, linking to its
 *  result. */
export function NeedsYouPanel({ needs }: { needs: readonly NeedsYou[] }): JSX.Element {
  const { t } = useTranslation()
  const language = useLanguage()
  const headingId = useId()
  return (
    <GlassPanel
      as="section"
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-3 px-6 py-6 xl:w-[380px] xl:shrink-0"
    >
      <h2 id={headingId} className="m-0 text-heading-small text-ink">
        {t('inventory.needs.heading', { count: needs.length })}
      </h2>
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {needs.map((need) => (
          <li key={need.tool.toolId}>
            <Link
              to="/app/inventory/$toolId"
              params={{ toolId: need.tool.toolId }}
              className="flex lift flex-col gap-1.5 rounded-card-small px-4 py-3 glass-thin focus-visible:outline-2 focus-visible:outline-lens-blue"
            >
              <span className="flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 font-semibold break-words text-ink">{need.tool.name}</span>
                <NeedPill need={need} />
              </span>
              <span className="text-caption text-slate">{action(t, need, language)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </GlassPanel>
  )
}
