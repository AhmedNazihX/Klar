import type { JSX } from 'react'
import { useTranslation } from 'react-i18next'

import type { ClassificationResult } from '@/api'
import { useToolTicks } from '@/hooks/use-tool-ticks'

import { DutiesSection, DutyList, ProviderDutiesPanel } from './ProviderDuties'
import { AlsoUsePanel, LighterPanel } from './ProviderNotes'
import { groupDuties } from './provider-layout'

/** The other role's duties, which "See the deployer duties" jumps to (one per screen). */
const OTHER_DUTIES_ID = 'role-duties'

/**
 * The provider layout's duties (artboard `ResultProvider`, P23), in place of the standard duty
 * list: the provider's duties in three groups, then the duties of the role it keeps (a
 * deployer's, when it also uses the system). On a legally ambiguous result `dutiesHeading`
 * frames the provider's duties as what the applied reading commits it to (P22).
 */
export function ProviderPanels({
  result,
  toolId,
  dutiesHeading,
}: {
  result: ClassificationResult
  toolId: string
  dutiesHeading?: string
}): JSX.Element {
  const { t } = useTranslation()
  const ticks = useToolTicks(toolId)
  const groups = groupDuties(result.obligations ?? [])
  // Ungrouped duties are the kept role's. A result saved before C9 grouped the duties has its
  // provider duties here too, under that role's heading when it keeps one (a known limit).
  const also = result.also_role
  const otherHeading = also && also !== 'provider' ? also : 'none'
  return (
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
      <ProviderDutiesPanel
        result={result}
        groups={groups}
        toolId={toolId}
        ticks={ticks}
        heading={dutiesHeading}
      />
      {groups.other.length > 0 && (
        <DutiesSection
          id={OTHER_DUTIES_ID}
          heading={t(`result.provider.otherHeading.${otherHeading}`)}
          duties={groups.other}
          done={ticks.done}
        >
          <DutyList duties={groups.other} result={result} toolId={toolId} ticks={ticks} />
        </DutiesSection>
      )}
    </div>
  )
}

/** The provider layout's side panels, above the facts: what makes it lighter, and "You also use
 *  it" with its link to the deployer duties when the result lists them. */
export function ProviderAside({ result }: { result: ClassificationResult }): JSX.Element {
  const hasOtherDuties = groupDuties(result.obligations ?? []).other.length > 0
  return (
    <>
      <LighterPanel result={result} />
      {result.also_role === 'deployer' && (
        <AlsoUsePanel dutiesId={hasOtherDuties ? OTHER_DUTIES_ID : null} />
      )}
    </>
  )
}
