// Legally ambiguous result fixtures (P22), typed from the generated client.
//
// fixtures/ambiguous.json is dumped from the backend with no model, database or network call,
// and backend/tests/drafting/test_frontend_ambiguous_fixture.py fails when it drifts (it says how
// to rewrite it): the recorded legally ambiguous result (own-e-09, a predictive-maintenance tool
// for cableways, whose Annex I safety-component question the law leaves open; an English
// description, bought by a deployer) and the request `POST /documents/vendor-letter` drafts from
// it in English and German with the tool's name "Ropeway wear forecast". The handler below serves
// the request and keeps what was asked.
import { http, HttpResponse, type HttpHandler } from 'msw'

import type {
  ClassificationResult,
  FollowUpQuestion,
  SettledBy,
  VendorLetter,
  VendorLetterRequest,
} from '@/api'
import type { Language } from '@/i18n'
import { env } from '@/lib/env'

import fixture from './fixtures/ambiguous.json'

const FIXTURE = fixture as unknown as {
  result: ClassificationResult
  letters: Record<Language, VendorLetter>
}

/** The recorded ambiguous result: high-risk assumed on the Annex I route, the amended text on
 *  30 Sep 2026, a deployer. Its question waits only for the Commission's guidelines. */
export const RECORDED_AMBIGUOUS: ClassificationResult = FIXTURE.result
export const REQUEST_LETTERS = FIXTURE.letters

export const VENDOR_LETTER_URL = `${env.apiUrl}/documents/vendor-letter`

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

/** A follow-up question the user can answer on the ambiguous result. */
export const SAFETY_QUESTION: FollowUpQuestion = {
  id: 'inspection_decisions',
  text: 'Does anyone defer a safety inspection because of the forecast?',
  hint: 'This decides whether the tool acts as a safety component.',
  options: ['yes', 'no', 'not_sure'],
}

/** The request as each language's handler answers it; `letterStatus` makes it fail. */
export function requestHandlers(
  letterBodies: VendorLetterRequest[],
  { letterStatus }: { letterStatus?: number } = {},
): HttpHandler[] {
  return [
    http.post(VENDOR_LETTER_URL, async ({ request }) => {
      const body = (await request.json()) as VendorLetterRequest
      letterBodies.push(body)
      if (letterStatus) return HttpResponse.json({ detail: 'refused' }, { status: letterStatus })
      return HttpResponse.json(REQUEST_LETTERS[body.language])
    }),
  ]
}
