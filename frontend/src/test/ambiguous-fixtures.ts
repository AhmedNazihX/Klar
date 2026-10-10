// Legally ambiguous result fixtures (P22), typed from the generated client.
//
// fixtures/ambiguous.json is dumped from the backend with no model, database or network call,
// and backend/tests/drafting/test_frontend_ambiguous_fixture.py fails when it drifts (it says how
// to rewrite it): the recorded legally ambiguous result (own-e-09, a predictive-maintenance tool
// for cableways, whose Annex I safety-component question the law leaves open; an English
// description, bought by a deployer) and the request `POST /documents/vendor-letter` drafts from
// it in English and German with the tool's name "Ropeway wear forecast", and the
// `GET /provisions/{id}` answers for Art. 6(1), the provision both readings cite, in both
// languages at the result's law version and date. The handlers below serve them and keep what
// was asked.
import { http, HttpResponse, type HttpHandler } from 'msw'

import type {
  ClassificationResult,
  FollowUpQuestion,
  Provision,
  SettledBy,
  VendorLetter,
  VendorLetterRequest,
} from '@/api'
import type { Language } from '@/i18n'
import { env } from '@/lib/env'

import fixture from './fixtures/ambiguous.json'
import { OWN_BRAND_PROVIDER } from './provider-fixtures'

const FIXTURE = fixture as unknown as {
  result: ClassificationResult
  letters: Record<Language, VendorLetter>
  provisions: Record<string, Record<Language, Provision>>
}

/** The recorded ambiguous result: high-risk assumed on the Annex I route, the amended text on
 *  30 Sep 2026, a deployer. Its question waits only for the Commission's guidelines. */
export const RECORDED_AMBIGUOUS: ClassificationResult = FIXTURE.result
export const REQUEST_LETTERS = FIXTURE.letters
export const AMBIGUOUS_PROVISIONS = FIXTURE.provisions

export const VENDOR_LETTER_URL = `${env.apiUrl}/documents/vendor-letter`
const PROVISION_URL = `${env.apiUrl}/provisions/:provisionId`

/** `result` with its open question's `settled_by` replaced. */
export function withSettledBy(
  result: ClassificationResult,
  settledBy: SettledBy[],
): ClassificationResult {
  return {
    ...result,
    steps: result.steps.map((step) =>
      step.open_question
        ? { ...step, open_question: { ...step.open_question, settled_by: settledBy } }
        : step,
    ),
  }
}

/** `result` with its route duties marked as Art. 111(2) leaves them (a tool already in use
 *  before the route date, decision 026 item 24). */
export function withLegacy(result: ClassificationResult): ClassificationResult {
  return {
    ...result,
    obligations: (result.obligations ?? []).map((obligation) =>
      obligation.high_risk_route ? { ...obligation, legacy: 'legacy_unchanged' } : obligation,
    ),
  }
}

/** The recorded result's route duties' date (2 August 2028 on the Annex I route). */
function recordedRouteDate(): string {
  const duty = (RECORDED_AMBIGUOUS.obligations ?? []).find(
    (obligation) => obligation.high_risk_route === 'annex_i',
  )
  if (!duty) throw new Error('The recorded ambiguous result has no Annex I duty.')
  return duty.applies_from
}

/** The recorded ambiguous result as a provider's (user decision 2026-10-10, option A): the role
 *  set to provider and the duties a provider's high-risk result lists, taken from the recorded
 *  own-brand provider (provider-fixtures.ts), moved to the recorded result's Annex I route and
 *  its date, as a provider's result on that route dates them. Its other duties (Art. 4 from
 *  2 February 2025) keep their dates. No recorded run is both. */
export function ambiguousProvider(): ClassificationResult {
  const routeDate = recordedRouteDate()
  return {
    ...RECORDED_AMBIGUOUS,
    role: 'provider',
    obligations: (OWN_BRAND_PROVIDER.obligations ?? []).map((obligation) =>
      obligation.high_risk_route
        ? { ...obligation, high_risk_route: 'annex_i', applies_from: routeDate }
        : obligation,
    ),
  }
}

/** A follow-up question on the open point (Art. 6(1)(a), which the open step cites). */
export const SAFETY_QUESTION: FollowUpQuestion = {
  id: 'inspection_decisions',
  text: 'Does anyone defer a safety inspection because of the forecast?',
  about: 'art:6:1:a',
  hint: 'This decides whether the tool acts as a safety component.',
  options: ['yes', 'no', 'not_sure'],
}

/** The request as each language's handler answers it, `letterStatus` making it fail; and each
 *  provision the fixture holds, at the recorded result's law version and date only (anything
 *  else is a 404), its id kept in `provisionIds`. */
export function requestHandlers(
  letterBodies: VendorLetterRequest[],
  { letterStatus, provisionIds = [] }: { letterStatus?: number; provisionIds?: string[] } = {},
): HttpHandler[] {
  return [
    http.get(PROVISION_URL, ({ request, params }) => {
      const query = new URL(request.url).searchParams
      const provisionId = String(params.provisionId)
      provisionIds.push(provisionId)
      const atResult =
        query.get('law_version') === RECORDED_AMBIGUOUS.law_version &&
        query.get('as_of') === RECORDED_AMBIGUOUS.as_of
      const provision = AMBIGUOUS_PROVISIONS[provisionId]?.[query.get('language') as Language]
      return atResult && provision
        ? HttpResponse.json(provision)
        : HttpResponse.json({ detail: 'no such text' }, { status: 404 })
    }),
    http.post(VENDOR_LETTER_URL, async ({ request }) => {
      const body = (await request.json()) as VendorLetterRequest
      letterBodies.push(body)
      if (letterStatus) return HttpResponse.json({ detail: 'refused' }, { status: letterStatus })
      return HttpResponse.json(REQUEST_LETTERS[body.language])
    }),
  ]
}
