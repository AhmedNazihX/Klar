import type { ClassificationResult, LawVersion, RiskClass, Role, Status } from '@/api'

// The landing page's agent example: what `classify_system` returns for the hero's worked example,
// trimmed to what the section is about (components.md › CodePanel). The keys are the generated
// `ClassificationResult`'s own, so the example can't drift from the API (LandingPage.test.tsx › the
// agent example also checks them against src/api/types.gen.ts). `steps` and the disclaimer are trimmed in words,
// in the page's language (landing.agents.steps, landing.agents.disclaimer).

/** A key of the result, in the order the example shows them. */
export type ExampleKey = keyof ClassificationResult

/** One line of the example: a key with a literal value, or a key whose value is trimmed in words. */
export type ExampleLine =
  | { key: ExampleKey; value: string; highlight?: boolean }
  | { key: ExampleKey; trimmed: 'steps' | 'disclaimer' }
  | { key: ExampleKey; object: Readonly<Record<string, string>> }

const RISK_CLASS: RiskClass = 'high_risk'
const STATUS: Status = 'decided'
const ROLE: Role = 'deployer'
const LAW_VERSION: LawVersion = 'amended'
// The consolidated text the amended version names (E12's law_text), trimmed to its CELEX number.
const LAW_TEXT: Pick<NonNullable<ClassificationResult['law_text']>, 'celex'> = {
  celex: '02024R1689-20260727',
}

export const CLASSIFY_EXAMPLE: readonly ExampleLine[] = [
  { key: 'risk_class', value: RISK_CLASS, highlight: true },
  { key: 'status', value: STATUS },
  { key: 'role', value: ROLE },
  { key: 'annex_point', value: 'annex:III:4:a' },
  { key: 'steps', trimmed: 'steps' },
  { key: 'law_version', value: LAW_VERSION },
  { key: 'law_text', object: LAW_TEXT },
  { key: 'disclaimer', trimmed: 'disclaimer' },
]
