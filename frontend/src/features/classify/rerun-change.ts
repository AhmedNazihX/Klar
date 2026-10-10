import type { TFunction } from 'i18next'

import type { ClassificationResult } from '@/api'
import { ambiguousProvision, openQuestionCount } from '@/features/inventory/tool-facts'
import type { Language } from '@/i18n'
import { riskClassOf } from '@/lib/risk-class'
import type { Answers } from '@/lib/tool-runs'

import { provisionName } from './provision-names'

// What a follow-up re-run changed (artboard `ResultRerun`): the class before and after, and the
// lines the Inventory, Obligations and "needs you" lists show for the tool, in the words those
// screens use. An assumed result keeps its stricter class and says so (it never looks settled).

/** Whether the answer changed the class or whether it is settled. */
export function hasResultChanged(
  before: ClassificationResult,
  after: ClassificationResult,
): boolean {
  return before.risk_class !== after.risk_class || before.status !== after.status
}

/** The class as the inventory's pill shows it: "High-risk", or "High-risk, assumed". */
export function classLabel(t: TFunction, result: ClassificationResult): string {
  const name = t(`pill.${riskClassOf(result)}`)
  return result.status === 'decided' ? name : t('inventory.table.assumedClass', { riskClass: name })
}

/** The tool's line in the obligations list: its duties, "possible" while the result is assumed. */
export function dutiesLabel(t: TFunction, result: ClassificationResult): string {
  const count = (result.obligations ?? []).filter((duty) => !duty.is_informational).length
  if (count === 0) return t('followUp.lists.noDuties')
  return result.status === 'decided'
    ? t('followUp.lists.duties', { count })
    : t('followUp.lists.possibleDuties', { count })
}

/** What the tool needs from the user, as the inventory's "needs you" list says it. */
export function needsLabel(t: TFunction, result: ClassificationResult, language: Language): string {
  if (result.risk_class === 'prohibited') return t('inventory.needs.prohibited')
  if (result.status === 'needs_more_information') {
    return t('inventory.needs.needsInfo', { count: openQuestionCount(result) })
  }
  if (result.status === 'legally_ambiguous') {
    const provision = ambiguousProvision(result)
    return provision
      ? t('inventory.needs.ambiguous', { provision: provisionName(provision, language) })
      : t('inventory.needs.ambiguousPlain')
  }
  return t('followUp.lists.nothing')
}

/** The answers this run added or changed since the run before, in the user's words. */
export function newAnswers(answers: Answers | undefined, before: Answers): string[] {
  return Object.entries(answers ?? {})
    .filter(([id, text]) => before[id] !== text)
    .map(([, text]) => text)
}
