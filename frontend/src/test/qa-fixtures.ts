import { http, HttpResponse } from 'msw'

import type { DocumentInfo, QaAnswer, QuestionRequest } from '@/api'
import { env } from '@/lib/env'

export const QA_URL = `${env.apiUrl}/qa`
export const DOCUMENTS_URL = `${env.apiUrl}/documents`

const DISCLAIMER_EN =
  'This is guidance, not legal advice. It is based only on the description provided and the ' +
  'version of the AI Act shown. Have decisions with legal consequences reviewed by a lawyer.'

/** An answer citing Art. 3(4) and a paragraph of the definition guidelines, as `POST /qa` sends
 *  it. */
export function answered(overrides: Partial<QaAnswer> = {}): QaAnswer {
  return {
    kind: 'answered',
    answer:
      'A deployer is anyone who uses an AI system under their own authority for work.\n\n' +
      'If your company uses a tool it bought, you are its deployer.',
    citations: [
      {
        provision_id: 'art:3:4',
        document_id: 'ai-act-consolidated',
        law_version: 'amended',
        document_status: 'consolidated',
        language: 'en',
        quote: "'deployer' means a natural or legal person using an AI system under its authority",
        english_only: false,
        changed_by_omnibus: false,
      },
      {
        provision_id: 'guide:guide-definition:para:12',
        document_id: 'guide-definition',
        law_version: null,
        document_status: 'draft',
        language: 'en',
        quote: 'The guidelines explain who uses a system under its own authority.',
        english_only: false,
        changed_by_omnibus: false,
      },
    ],
    language: 'en',
    law_version: 'amended',
    as_of: '2026-10-10',
    disclaimer: DISCLAIMER_EN,
    ...overrides,
  }
}

/** The fixed answer to a question the corpus doesn't cover: no citation. */
export function outsideCorpus(): QaAnswer {
  return answered({
    kind: 'outside_corpus',
    answer:
      "That's outside what I can answer. I cover the AI Act and the Commission's guidance on " +
      "it, and they don't answer this question.",
    citations: [],
  })
}

export const DOCUMENTS: DocumentInfo[] = [
  {
    doc_key: 'ai-act-consolidated',
    title: 'AI Act, consolidated 27 Jul 2026',
    celex: '02024R1689-20260727',
    doc_type: 'law',
    status: 'consolidated',
    law_version: 'amended',
    is_amending: false,
    language: 'en',
    english_only: false,
    published_on: '2026-07-27',
    in_force_from: '2026-07-27',
  },
  {
    doc_key: 'ai-act',
    title: 'Regulation (EU) 2024/1689',
    celex: '32024R1689',
    doc_type: 'law',
    status: 'final',
    law_version: 'original',
    is_amending: false,
    language: 'en',
    english_only: false,
    published_on: '2024-07-12',
    in_force_from: '2024-08-01',
  },
  {
    doc_key: 'omnibus',
    title: 'Regulation (EU) 2026/1744',
    celex: '32026R1744',
    doc_type: 'law',
    status: 'final',
    law_version: 'amended',
    is_amending: true,
    language: 'en',
    english_only: false,
    published_on: '2026-07-20',
    in_force_from: '2026-07-27',
  },
  {
    doc_key: 'guide-high-risk-annex-iii',
    title: 'Guidelines on high-risk classification',
    celex: null,
    doc_type: 'guideline',
    status: 'draft',
    law_version: null,
    is_amending: false,
    language: 'en',
    english_only: false,
    published_on: '2026-05-19',
    in_force_from: null,
  },
]

/** The texts as `GET /documents?language=de` lists them: German rows under their German titles,
 *  a text only in English under its English title, marked. */
export const DOCUMENTS_DE: DocumentInfo[] = [
  {
    ...(DOCUMENTS[0] as DocumentInfo),
    title: 'KI-Verordnung, konsolidierte Fassung vom 27. Juli 2026',
    language: 'de',
  },
  {
    ...(DOCUMENTS[3] as DocumentInfo),
    english_only: true,
  },
]

/** `POST /qa` answering each question with `reply` (an answer, or an HTTP status), noting each
 *  request's body in `sent`; and `GET /documents` with `DOCUMENTS`. */
export function qaHandlers(sent: QuestionRequest[], reply: () => QaAnswer | number) {
  return [
    http.post(QA_URL, async ({ request }) => {
      sent.push((await request.json()) as QuestionRequest)
      const answer = reply()
      if (typeof answer === 'number') {
        return HttpResponse.json({ detail: 'refused' }, { status: answer })
      }
      return HttpResponse.json(answer)
    }),
    http.get(DOCUMENTS_URL, ({ request }) => {
      const isGerman = new URL(request.url).searchParams.get('language') === 'de'
      return HttpResponse.json({ documents: isGerman ? DOCUMENTS_DE : DOCUMENTS, disclaimer: 'x' })
    }),
  ]
}
