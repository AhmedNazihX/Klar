import { screen } from '@testing-library/react'
import i18n from 'i18next'
import { describe, expect, it } from 'vitest'

import type { DocumentKind, InterviewQuestion } from '@/api'
import { renderWithProviders } from '@/test/test-utils'

import { AnswerForm, type Requirement } from './AnswerForm'

const QUESTION: InterviewQuestion = {
  key: 'vendor',
  text: 'Who is the vendor?',
  section: 'vendor',
  choices: [],
}

async function hintFor(
  kind: DocumentKind,
  language: 'en' | 'de',
  requirement: Requirement | null = null,
): Promise<string | null> {
  await i18n.changeLanguage(language)
  renderWithProviders(
    <AnswerForm
      question={QUESTION}
      given=""
      kind={kind}
      isLong={false}
      requirement={requirement}
      isSaving={false}
      onSave={() => undefined}
      onSkip={() => undefined}
    />,
  )
  const field = await screen.findByRole('textbox', { name: QUESTION.text })
  const hintId = field.getAttribute('aria-describedby') ?? ''
  return document.getElementById(hintId)?.textContent ?? null
}

describe('the hint under an answer', () => {
  it.each([
    [
      'notice',
      'en',
      "Written into the notice as you give it. Klar won't add anything you didn't say.",
    ],
    [
      'record',
      'en',
      "Written into the record as you give it. Klar won't add anything you didn't say.",
    ],
    [
      'disclosure',
      'en',
      "Written into the disclosure as you give it. Klar won't add anything you didn't say.",
    ],
    [
      'letter',
      'en',
      "Written into the letter as you give it. Klar won't add anything you didn't say.",
    ],
    [
      'skeleton',
      'en',
      "Written in as you give it, as a sentence. Klar won't add anything you didn't say.",
    ],
    [
      'notice',
      'de',
      'So in den Hinweis übernommen, wie Sie es angeben. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    ],
    [
      'record',
      'de',
      'So in den Nachweis übernommen, wie Sie es angeben. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    ],
    [
      'disclosure',
      'de',
      'So in den Hinweis übernommen, wie Sie es angeben. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    ],
    [
      'letter',
      'de',
      'So in das Schreiben übernommen, wie Sie es angeben. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    ],
    [
      'skeleton',
      'de',
      'So übernommen, wie Sie es angeben, als Satz. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    ],
  ] as const)('names what a %s answer is written into (%s)', async (kind, language, hint) => {
    expect(await hintFor(kind, language)).toBe(hint)
  })

  it.each([
    [
      'en',
      { provision: 'Annex IV 2', section: 'Elements and development process' },
      "Annex IV 2: Elements and development process. Written in as you give it, as a sentence. Klar won't add anything you didn't say.",
    ],
    [
      'de',
      { provision: 'Anhang IV Nr. 2', section: 'Elemente und Entwicklungsprozess' },
      'Anhang IV Nr. 2: Elemente und Entwicklungsprozess. So übernommen, wie Sie es angeben, als Satz. Klar fügt nichts hinzu, was Sie nicht gesagt haben.',
    ],
  ] as const)(
    "names the skeleton's requirement the question answers (%s)",
    async (language, requirement, hint) => {
      expect(await hintFor('skeleton', language, requirement)).toBe(hint)
    },
  )
})
