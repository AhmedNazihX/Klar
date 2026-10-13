// The reviewer view's parts beyond the steps (P31): "Texts used" under "Questions about this
// result" (artboard `Reviewer`), and a decided ban's steps after Art. 5, each as a card that says
// it wasn't checked (artboard `ResultProhibited`, as the summary's rows say).
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Citation, ClassificationResult, DocumentInfo } from '@/api'
import type { Language } from '@/i18n'
import { WORKED_EXAMPLE, WORKED_EXAMPLE_DESCRIPTION } from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { RECORDED_PROHIBITED, prohibitedHandlers } from '@/test/prohibited-fixtures'
import { corpusDocumentsHandler, DOCUMENTS, DOCUMENTS_URL } from '@/test/qa-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { putRun } from './classification-store'

const TOOL_ID = 'applicant-screening'
const TOOL_NAME = 'Applicant screening'

async function openReviewer(
  result: ClassificationResult,
  language: Language,
  documents?: DocumentInfo[],
): Promise<void> {
  server.use(corpusDocumentsHandler(), ...prohibitedHandlers({ lookups: [], letterBodies: [] }))
  if (documents) {
    server.use(http.get(DOCUMENTS_URL, () => HttpResponse.json({ documents, disclaimer: 'x' })))
  }
  await i18n.changeLanguage(language)
  const client = createTestQueryClient()
  putRun(client, {
    toolId: TOOL_ID,
    name: TOOL_NAME,
    description: WORKED_EXAMPLE_DESCRIPTION,
    result,
  })
  renderRoute(`/app/inventory/${TOOL_ID}?view=reviewer`, client)
  await screen.findByRole('heading', { level: 1, name: TOOL_NAME })
}

/** `result` with a quote from `documentId` cited first on its first step. */
function alsoCiting(result: ClassificationResult, documentId: string): ClassificationResult {
  const [first, ...rest] = result.steps
  if (!first) throw new Error('The result has no step.')
  const quote: Citation = {
    provision_id: 'guide:x:para:1',
    document_id: documentId,
    language: 'en',
    quote: 'q',
    changed_by_omnibus: false,
  }
  return {
    ...result,
    steps: [{ ...first, citations: [quote, ...(first.citations ?? [])] }, ...rest],
  }
}

/** Each listed text as "title, kind", in order. */
async function textsUsed(heading: string): Promise<string[]> {
  const panel = screen.getByRole('region', { name: heading })
  await within(panel).findByRole('list')
  return within(panel)
    .getAllByRole('listitem')
    .map((item) => item.textContent)
}

describe('Texts used', () => {
  it('lists the texts the amended result quotes with their status, under the questions', async () => {
    // The worked example quotes the consolidated Act, marked where the Omnibus changed it, and a
    // recital of the original Regulation, which the amended text leaves out; it quotes no
    // guidance, so the guidelines the corpus also holds aren't listed.
    await openReviewer(WORKED_EXAMPLE, 'en')
    expect(await textsUsed('Texts used')).toEqual([
      'AI Act, consolidated 27 Jul 2026Consolidation',
      'Regulation (EU) 2026/1744Law',
    ])
    const questions = screen.getByRole('region', { name: 'Questions about this result' })
    const texts = screen.getByRole('region', { name: 'Texts used' })
    expect(questions.compareDocumentPosition(texts) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('lists the law before the guidance, whatever order the result quotes them in', async () => {
    await openReviewer(alsoCiting(WORKED_EXAMPLE, 'guide-high-risk-annex-iii'), 'en')
    expect(await textsUsed('Texts used')).toEqual([
      'AI Act, consolidated 27 Jul 2026Consolidation',
      'Regulation (EU) 2026/1744Law',
      'Guidelines on high-risk classificationDraft',
    ])
  })

  it('lists only the original texts for a result run under the original Act', async () => {
    // An amending act without a law version, quoted by the result, stays hidden under the
    // original text, as the amended consolidation and the Omnibus do.
    const amending: DocumentInfo = {
      ...(DOCUMENTS[2] as DocumentInfo),
      doc_key: 'amending-act',
      title: 'An amending act',
      law_version: null,
      is_amending: true,
    }
    const result = alsoCiting({ ...WORKED_EXAMPLE, law_version: 'original' }, 'amending-act')
    await openReviewer(result, 'en', [...DOCUMENTS, amending])
    expect(await textsUsed('Texts used')).toEqual(['Regulation (EU) 2024/1689Law'])
  })

  it('reads in German, a text only in English marked as such', async () => {
    await openReviewer(alsoCiting(WORKED_EXAMPLE, 'guide-high-risk-annex-iii'), 'de')
    expect(await textsUsed('Verwendete Texte')).toEqual([
      'KI-Verordnung, konsolidierte Fassung vom 27. Juli 2026Konsolidierte Fassung',
      'Guidelines on high-risk classificationnur auf EnglischEntwurf',
    ])
  })
})

describe('the reviewer view of a decided ban', () => {
  it.each([
    [
      'en',
      ['Role', '3 High-risk', '4 Transparency', 'Duties'],
      'Not checked: a ban ends the checks',
    ],
    [
      'de',
      ['Rolle', '3 Hochrisiko', '4 Transparenz', 'Pflichten'],
      'Nicht geprüft: Ein Verbot beendet die Prüfung',
    ],
  ] as const)(
    'shows every step after Art. 5 as not checked (%s)',
    async (language, names, line) => {
      await openReviewer(RECORDED_PROHIBITED, language)
      const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
      for (const name of names) {
        expect(headings).toContain(name)
        const card = screen.getByRole('heading', { level: 2, name }).closest('article')
        expect(card, name).toHaveTextContent(line)
      }
    },
  )
})
