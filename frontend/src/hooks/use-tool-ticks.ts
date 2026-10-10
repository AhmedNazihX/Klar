import { ticksOn } from '@/features/obligations/obligation-list'

import { useDutyTicks, useToggleDutyTick } from './use-duty-progress'

/** One tool's saved ticks and the toggle that saves a change. */
export type ToolTicks = {
  /** The obligation keys ticked off on the tool. */
  done: ReadonlySet<string>
  onTick: (key: string, isDone: boolean) => void
}

/**
 * One tool's duty ticks, through the Obligations screen's hooks (P24), so a box ticked on the
 * result shows there too; whether reading them or saving the last change failed.
 */
export function useToolTicks(
  toolId: string,
): ToolTicks & { hasReadFailed: boolean; hasSaveFailed: boolean } {
  const ticks = useDutyTicks()
  const toggle = useToggleDutyTick()
  return {
    done: ticksOn(ticks.data ?? [], toolId),
    onTick: (key, isDone) => {
      toggle.mutate({ toolId, obligationKey: key, isDone })
    },
    hasReadFailed: ticks.isError,
    hasSaveFailed: toggle.isError,
  }
}
