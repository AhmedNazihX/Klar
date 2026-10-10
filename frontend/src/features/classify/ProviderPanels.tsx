import type { JSX, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { useToolTicks } from '@/hooks/use-tool-ticks'

import { DutiesSection, DutyList, ProviderDutiesPanel } from './ProviderDuties'
import { AlsoUsePanel, LighterPanel } from './ProviderNotes'
import { groupDuties } from './provider-layout'

/** The other role's duties, which "See the deployer duties" jumps to (one per screen). */
const OTHER_DUTIES_ID = 'role-duties'

/**
 * The provider layout's panels (artboard `ResultProvider`, P23), in place of the standard duty
 * list: the provider's duties in three groups, then the duties of the role it keeps (a deployer's,
 * when it also uses the system); beside them what makes it lighter, "You also use it", and the
 * facts the result rests on (`facts`).
 */
export function ProviderPanels({
  result,
  toolId,
  facts,
}: {
  result: ClassificationResult
  toolId: string
  /** The facts panel, which goes last in the side column. */
  facts: ReactNode
}): JSX.Element {
  const { t } = useTranslation()
  const ticks = useToolTicks(toolId)
  const groups = groupDuties(result.obligations ?? [])
  const also = result.also_role
  const otherHeading = also && also !== 'provider' ? also : 'none'
  return (
    <div className="flex min-w-0 flex-col items-stretch gap-5 xl:flex-row xl:items-start">
      <div className="flex min-w-0 flex-1 flex-col gap-5">
        {ticks.hasReadFailed && (
          <p role="alert" className="m-0 text-body-small text-risk-prohibited">
            {t('result.provider.ticksFailed')}
          </p>
        )}
        {ticks.hasSaveFailed && (
          <p role="alert" className="m-0 text-body-small text-risk-prohibited">
            {t('obligations.saveFailed')}
          </p>
        )}
        <ProviderDutiesPanel result={result} groups={groups} toolId={toolId} ticks={ticks} />
        {groups.other.length > 0 && (
          <DutiesSection
            id={OTHER_DUTIES_ID}
            heading={t(`result.provider.otherHeading.${otherHeading}`)}
            toolId={toolId}
            duties={groups.other}
          >
            <DutyList duties={groups.other} toolId={toolId} ticks={ticks} />
          </DutiesSection>
        )}
      </div>
      <div className="flex min-w-0 flex-col gap-5 xl:w-[380px] xl:shrink-0">
        <LighterPanel result={result} />
        {also === 'deployer' && (
          <AlsoUsePanel dutiesId={groups.other.length > 0 ? OTHER_DUTIES_ID : null} />
        )}
        {facts}
      </div>
    </div>
  )
}
