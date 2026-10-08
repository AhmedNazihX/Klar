import type { ClassificationResult, RiskClass } from '@/api'

/**
 * A result's class. Only a needs-a-description result (E13: the description was too thin to
 * start, so no check ran) has none, and it never reaches a screen that shows a class: the
 * classify run stops on it (P20 shows its three prompts) and a stored result always has one.
 */
export function riskClassOf(result: ClassificationResult): RiskClass {
  if (result.risk_class === null) {
    throw new Error('A needs-a-description result has no class to show.')
  }
  return result.risk_class
}
