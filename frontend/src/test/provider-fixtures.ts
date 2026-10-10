// Provider results for the provider layout (P23), typed from the generated client.
//
// fixtures/provider.json holds, by own case id, the result of a run whose role step is the one
// `test_role_obligations.py` recorded for that case (finalised by the engine, with the class the
// case's label gives), dumped and drift-checked by
// backend/tests/engine/test_frontend_provider_fixture.py.
import type { ClassificationResult } from '@/api'

import fixture from './fixtures/provider.json'

const FIXTURE = fixture as unknown as Record<string, ClassificationResult>

function recorded(caseId: string): ClassificationResult {
  const result = FIXTURE[caseId]
  if (!result) throw new Error(`fixtures/provider.json has no ${caseId}`)
  return result
}

/** own-d-01 (English): a recruitment agency selling a licensed screening tool under its own
 *  brand; the provider under Art. 25(1)(a), high-risk under Annex III point 4(a). */
export const OWN_BRAND_PROVIDER = recorded('own-d-01-own-brand-screening')

/** own-d-13 (German): a welfare office that extended a bought mailroom tool to housing benefit;
 *  the provider under Art. 25(1)(c) and also the deployer, Annex III point 5(a). */
export const PROVIDER_ALSO_DEPLOYER = recorded('own-d-13-mailroom-tool-benefits')

/** own-d-03 (English): a hiring workflow built on a general-purpose AI assistant; the provider
 *  through the GPAI build route (Art. 3(68)), high-risk under Annex III point 4(a). */
export const GPAI_HIGH_RISK = recorded('own-d-03-assistant-repurposed-hiring')

/** own-d-06 (German): a shop chat built on a third-party large language model; the provider
 *  through the GPAI build route, limited risk (Art. 50(1)). */
export const GPAI_LIMITED = recorded('own-d-06-shop-chat-on-llm')
