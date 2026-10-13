// The reviewer view's parts beyond the steps (P31): "Texts used" under "Questions about this
// result" (artboard `Reviewer`), and a decided ban's steps after Art. 5, each as a card that says
// it wasn't checked (artboard `ResultProhibited`, as the summary's rows say).
import { screen, within } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import type { ClassificationResult } from '@/api'
import type { Language } from '@/i18n'
import { WORKED_EXAMPLE, WORKED_EXAMPLE_DESCRIPTION } from '@/test/classify-fixtures'
import { server } from '@/test/msw-server'
import { RECORDED_PROHIBITED, prohibitedHandlers } from '@/test/prohibited-fixtures'
import { corpusDocumentsHandler } from '@/test/qa-fixtures'
import { createTestQueryClient, renderRoute } from '@/test/test-utils'

import { putRun } from './classification-store'

const TOOL_ID = 'applicant-screening'
const TOOL_NAME = 'Applicant screening'

async function openReviewer(result: ClassificationResult, language: Language): Promise<void> {
  server.use(corpusDocumentsHandler(), ...prohibitedHandlers({ lookups: [], letterBodies: [] }))
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

/** Each listed text as "title, kind", in order. */
async function textsUsed(heading: string): Promise<string[]> {
  const panel = screen.getByRole('region', { name: heading })
  await within(panel).findByRole('list')
  return within(panel)
    .getAllByRole('listitem')
    .map((item) => item.textContent)
}

describe('Texts used', () => {
  it('lists the texts of the amended Act with their status, under the questions', async () => {
    await openReviewer(WORKED_EXAMPLE, 'en')
    expect(await textsUsed('Texts used')).toEqual([
      'AI Act, consolidated 27 Jul 2026Consolidation',
      'Regulation (EU) 2026/1744Law',
      'Guidelines on high-risk classificationDraft',
    ])
    const questions = screen.getByRole('region', { name: 'Questions about this result' })
    const texts = screen.getByRole('region', { name: 'Texts used' })
    expect(questions.compareDocumentPosition(texts) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('lists the original texts for a result run under the original Act', async () => {
    await openReviewer({ ...WORKED_EXAMPLE, law_version: 'original' }, 'en')
    expect(await textsUsed('Texts used')).toEqual([
      'Regulation (EU) 2024/1689Law',
      'Guidelines on high-risk classificationDraft',
    ])
  })

  it('reads in German, a text only in English marked as such', async () => {
    await openReviewer(WORKED_EXAMPLE, 'de')
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
