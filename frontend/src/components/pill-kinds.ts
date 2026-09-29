/**
 * The seven looks a pill can take: the five risk classes and the two uncertain statuses.
 * The keys are the API's `RiskClass` and `Status` values, so a result maps onto a pill directly.
 * This is a presentation key, not the API type; views take `RiskClass`/`Status` from the
 * generated client (src/api/) and pass the value in.
 */
export const PILL_KINDS = [
  'prohibited',
  'high_risk',
  'limited_risk',
  'minimal_risk',
  'out_of_scope',
  'legally_ambiguous',
  'needs_more_information',
] as const
export type PillKind = (typeof PILL_KINDS)[number]
