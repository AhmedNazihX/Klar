// Prohibited-result fixtures (P21), typed from the generated client.
//
// fixtures/prohibited.json is dumped from the backend with no model, database or network call,
// and backend/tests/drafting/test_frontend_prohibited_fixture.py fails when it drifts (it says
// how to rewrite it): the recorded prohibited result (own-c-08, a call centre's software reading
// its staff's moods from their voices, decided under Art. 5(1)(f); a German description, so its
// facts and decision are German), the vendor message `POST /documents/vendor-letter` drafts
// from it in English and German with the tool's name "Call mood scoring" (the screen's answer to
// "The tool"), and the `GET /provisions/{id}` answers for Art. 5(1)(f),
// Art. 99(3) and Art. 99(6) in both languages at the result's law version and date. The
// handlers below serve them and keep what was asked.
import { http, HttpResponse, type HttpHandler } from 'msw'

import type { ClassificationResult, Provision, VendorLetter, VendorLetterRequest } from '@/api'
import type { Language } from '@/i18n'
import { env } from '@/lib/env'

import fixture from './fixtures/prohibited.json'

const FIXTURE = fixture as unknown as {
  result: ClassificationResult
  letters: Record<Language, VendorLetter>
  provisions: Record<string, Record<Language, Provision>>
}

/** The recorded prohibited result: decided, Art. 5(1)(f), the amended text on 30 Sep 2026. */
export const RECORDED_PROHIBITED: ClassificationResult = FIXTURE.result
export const VENDOR_LETTERS = FIXTURE.letters
export const PROVISIONS = FIXTURE.provisions

export const PROVISION_URL = `${env.apiUrl}/provisions/:provisionId`
export const VENDOR_LETTER_URL = `${env.apiUrl}/documents/vendor-letter`

/** One provision lookup as the screen sent it. */
export type ProvisionLookup = {
  provisionId: string
  language: string | null
  lawVersion: string | null
  asOf: string | null
}

export type ProhibitedTraffic = {
  lookups: ProvisionLookup[]
  letterBodies: VendorLetterRequest[]
}

/** The API's answers for the prohibited screen: each provision the fixture holds, at the
 *  recorded result's law version and date only (anything else is a 404), and the vendor letter
 *  in the language asked for. `letterStatus` or `provisionStatus` makes those requests fail. */
export function prohibitedHandlers(
  traffic: ProhibitedTraffic,
  { letterStatus, provisionStatus }: { letterStatus?: number; provisionStatus?: number } = {},
): HttpHandler[] {
  return [
    http.get(PROVISION_URL, ({ request, params }) => {
      const query = new URL(request.url).searchParams
      const lookup: ProvisionLookup = {
        provisionId: String(params.provisionId),
        language: query.get('language'),
        lawVersion: query.get('law_version'),
        asOf: query.get('as_of'),
      }
      traffic.lookups.push(lookup)
      if (provisionStatus) return HttpResponse.json({}, { status: provisionStatus })
      const atResult =
        lookup.lawVersion === RECORDED_PROHIBITED.law_version &&
        lookup.asOf === RECORDED_PROHIBITED.as_of
      const provision = PROVISIONS[lookup.provisionId]?.[lookup.language as Language]
      return atResult && provision
        ? HttpResponse.json(provision)
        : HttpResponse.json({ detail: 'no such text' }, { status: 404 })
    }),
    http.post(VENDOR_LETTER_URL, async ({ request }) => {
      const body = (await request.json()) as VendorLetterRequest
      traffic.letterBodies.push(body)
      if (letterStatus) return HttpResponse.json({ detail: 'refused' }, { status: letterStatus })
      return HttpResponse.json(VENDOR_LETTERS[body.language])
    }),
  ]
}
