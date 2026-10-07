// Draft-document fixtures for the Documents screen (P9), typed from the generated client.
//
// fixtures/documents.drafts.json holds what `POST /documents/drafts` returned, dumped from the
// backend's own drafter (aiact.drafting.documents.checked_drafts) with no model call: the
// recorded worked example as a deployer (no answers; one answer to the workers notice; German),
// and the backend tests' provider result with its skeletons for an SME (no answers; one answer
// to Annex IV). The Supabase and API handlers below serve them.
import { http, HttpResponse, type HttpHandler } from 'msw'

import type { CheckedDraft, ClassificationResult } from '@/api'
import { env } from '@/lib/env'

import drafts from './fixtures/documents.drafts.json'
import { SUPABASE_URL } from './supabase-fixtures'

type DraftSet = readonly CheckedDraft[]

const FIXTURE = drafts as unknown as {
  provider_result: ClassificationResult
  deployer: { en: DraftSet; en_answered: DraftSet; de: DraftSet }
  provider: { en: DraftSet; en_answered: DraftSet }
}

export const DEPLOYER_DRAFTS = FIXTURE.deployer
export const PROVIDER_DRAFTS = FIXTURE.provider
export const PROVIDER_RESULT = FIXTURE.provider_result

/** The answers the "answered" fixtures were drafted with. */
export const WORKERS_TOOL_ANSWER = 'TalentRank, supplied by Rank GmbH.'
export const ANNEX_IV_ANSWER = 'scores drivers for bonuses'

export const DRAFTS_URL = `${env.apiUrl}/documents/drafts`
export const EXPORT_URL = `${env.apiUrl}/documents/export`
export const ANSWERS_URL = `${SUPABASE_URL}/rest/v1/interview_answers`

export type AnswerRow = { template: string; question_key: string; answer: string }

type DraftsBody = {
  result: ClassificationResult
  language: 'en' | 'de'
  size_class: string | null
  answers: Record<string, Record<string, string>>
}

/** The fixture `POST /documents/drafts` would answer `body` with. */
function draftsFor(body: DraftsBody): DraftSet {
  if (body.result.role === 'provider') {
    const answered = body.answers.annex_iv_technical_documentation?.intended_purpose
    return answered ? PROVIDER_DRAFTS.en_answered : PROVIDER_DRAFTS.en
  }
  if (body.language === 'de') return DEPLOYER_DRAFTS.de
  const answered = body.answers.art_26_7_workers?.tool_and_supplier
  return answered ? DEPLOYER_DRAFTS.en_answered : DEPLOYER_DRAFTS.en
}

/** What the handlers saw, for the tests to assert on. */
export type DocumentsTraffic = {
  draftBodies: DraftsBody[]
  savedAnswers: { body: unknown; onConflict: string | null }[]
  exports: unknown[]
}

/** The interview's stored answers (`rows`), the upsert that saves one, and the drafts API. */
export function documentsHandlers(
  rows: () => AnswerRow[],
  traffic: DocumentsTraffic,
): HttpHandler[] {
  return [
    http.get(ANSWERS_URL, () => HttpResponse.json(rows())),
    http.post(ANSWERS_URL, async ({ request }) => {
      const body = await request.json()
      traffic.savedAnswers.push({
        body,
        onConflict: new URL(request.url).searchParams.get('on_conflict'),
      })
      return new HttpResponse(null, { status: 201 })
    }),
    http.post(DRAFTS_URL, async ({ request }) => {
      const body = (await request.json()) as DraftsBody
      traffic.draftBodies.push(body)
      return HttpResponse.json({ documents: draftsFor(body) })
    }),
  ]
}
