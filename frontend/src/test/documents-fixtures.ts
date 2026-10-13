// Document fixtures for the Documents screen (P9), typed from the generated client.
//
// fixtures/documents.drafts.json holds what `POST /documents/list` and `POST /documents/draft`
// return, dumped from the backend's own drafter (aiact.drafting.documents: listed_documents and
// checked_draft) with no model call: the recorded worked example as a deployer (no answers; one
// answer to the workers notice; German), the backend tests' provider result with its skeletons
// for an SME (no answers; one answer to Annex IV), and a limited-risk result with the Art. 50(3)
// disclosure (no answer; "both" chosen, in English and German). Each draft set is keyed by
// template id. The Supabase and API handlers below serve them.
import { http, HttpResponse, type HttpHandler } from 'msw'

import type { CheckedDraft, ClassificationResult, ListedDocument } from '@/api'
import { env } from '@/lib/env'

import fixture from './fixtures/documents.drafts.json'
import { SUPABASE_URL } from './supabase-fixtures'

type Drafts = Readonly<Record<string, CheckedDraft>>
type Lists = { en: { documents: ListedDocument[] }; de: { documents: ListedDocument[] } }
type ResultDocuments = {
  list: Lists
  en: Drafts
  en_answered: Drafts
  de?: Drafts
  de_answered?: Drafts
}

const FIXTURE = fixture as unknown as {
  provider_result: ClassificationResult
  limited_result: ClassificationResult
  deployer: ResultDocuments
  provider: ResultDocuments
  limited: ResultDocuments
}

export const DEPLOYER_DOCUMENTS = FIXTURE.deployer
export const PROVIDER_DOCUMENTS = FIXTURE.provider
export const LIMITED_DOCUMENTS = FIXTURE.limited
export const PROVIDER_RESULT = FIXTURE.provider_result
export const LIMITED_RESULT = FIXTURE.limited_result

/** The answers the "answered" fixtures were drafted with. */
export const WORKERS_TOOL_ANSWER = 'TalentRank, supplied by Rank GmbH.'
export const ANNEX_IV_ANSWER = 'scores drivers for bonuses'
export const ART_50_3_CHOICE = 'both'

export const LIST_URL = `${env.apiUrl}/documents/list`
export const DRAFT_URL = `${env.apiUrl}/documents/draft`
export const EXPORT_URL = `${env.apiUrl}/documents/export`
export const ANSWERS_URL = `${SUPABASE_URL}/rest/v1/interview_answers`

export type AnswerRow = { template: string; question_key: string; answer: string }

export type ListBody = { result: ClassificationResult; language: 'en' | 'de' }
export type DraftBody = ListBody & {
  template: string
  size_class: string | null
  answers: Record<string, string>
}

function documentsOf(result: ClassificationResult): ResultDocuments {
  if (result.role === 'provider') return PROVIDER_DOCUMENTS
  if (result.risk_class === 'limited_risk') return LIMITED_DOCUMENTS
  return DEPLOYER_DOCUMENTS
}

/** The fixture `POST /documents/draft` would answer `body` with. The provider's drafts, and the
 *  deployer's answered ones, are English only: a German screen shows them with its own words in
 *  German. */
function draftFor(body: DraftBody): CheckedDraft | undefined {
  const documents = documentsOf(body.result)
  const answered = Object.values(body.answers).some((answer) => answer.trim() !== '')
  const germanAnswered = body.language === 'de' ? documents.de_answered?.[body.template] : null
  if (answered && germanAnswered) return germanAnswered
  if (answered) return documents.en_answered[body.template] ?? documents.en[body.template]
  if (body.language === 'de' && documents.de) return documents.de[body.template]
  return documents.en[body.template]
}

/** What the handlers saw, for the tests to assert on. */
export type DocumentsTraffic = {
  listBodies: ListBody[]
  draftBodies: DraftBody[]
  savedAnswers: { body: unknown; onConflict: string | null }[]
  exports: unknown[]
}

export function newTraffic(): DocumentsTraffic {
  return { listBodies: [], draftBodies: [], savedAnswers: [], exports: [] }
}

/** The interview's stored answers (`rows`), the upsert that saves one, and the documents API. */
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
    http.post(LIST_URL, async ({ request }) => {
      const body = (await request.json()) as ListBody
      traffic.listBodies.push(body)
      return HttpResponse.json(documentsOf(body.result).list[body.language])
    }),
    http.post(DRAFT_URL, async ({ request }) => {
      const body = (await request.json()) as DraftBody
      traffic.draftBodies.push(body)
      const draft = draftFor(body)
      return draft
        ? HttpResponse.json(draft)
        : HttpResponse.json({ detail: 'no such document' }, { status: 404 })
    }),
  ]
}
