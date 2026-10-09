import type { ClassificationResult, RiskClass } from '@/api'

/**
 * Whether a result has a class Klar may show or export: a class, and every check assessed. A
 * result stored before decision 030 can list a check the model provider refused
 * (`not_assessed`) next to the class it assumed; that class rests on a check nobody assessed, so
 * it is treated like a result with no class ("not classified yet"), as the API's
 * `assessed_class` treats it in reports and documents.
 */
export function hasAssessedClass(result: ClassificationResult): boolean {
  return result.risk_class !== null && (result.not_assessed ?? []).length === 0
}

/**
 * A result's class. A result without an assessed class (`hasAssessedClass`) never reaches a
 * screen that shows a class: the classify run stops on it (P20 shows a needs-a-description
 * result's three prompts, a refused check its own panel), and a stored one is read as a tool
 * with no result (`lib/inventory.ts`).
 */
export function riskClassOf(result: ClassificationResult): RiskClass {
  if (result.risk_class === null || !hasAssessedClass(result)) {
    throw new Error('A result without an assessed class has no class to show.')
  }
  return result.risk_class
}
