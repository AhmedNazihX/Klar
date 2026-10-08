// Original-text fixtures (P10): one description's result under the amended text and under the
// original 2024 text (decision 020), for "Original Act vs amended". Like classify-fixtures.ts'
// variants they are hand-made from the recorded worked example, changing only the fields the
// comparison reads; they are fixtures, not engine output. The quotes are the corpus's own text
// (data/parsed), and each pair follows a rule E11 tested under both texts: the Art. 5(1)(ba) ban
// the Omnibus added, and machinery moving from Annex I Section A to Section B (own-e-04).
import type { Citation, ClassificationResult, LawText, StepResult } from '@/api'

import { decidedHighRisk } from './classify-fixtures'

const ORIGINAL_LAW_TEXT: LawText = {
  document_id: 'ai-act',
  celex: '32024R1689',
  version_date: '2024-06-13',
}

/** A result as the engine gives it under the original text: no duties (decision 020). */
function underOriginal(result: ClassificationResult): ClassificationResult {
  return {
    ...result,
    law_version: 'original',
    law_text: ORIGINAL_LAW_TEXT,
    obligations: [],
    steps: result.steps.map((step) => ({
      ...step,
      citations: (step.citations ?? []).map((citation) => ({
        ...citation,
        document_id: 'ai-act',
        law_version: 'original' as const,
        changed_by_omnibus: false,
      })),
    })),
  }
}

function step(base: ClassificationResult, name: StepResult['step'], change: Partial<StepResult>) {
  const found = base.steps.find((candidate) => candidate.step === name)
  if (!found) throw new Error(`The recorded result has a ${name} step.`)
  return { ...found, status: 'decided' as const, missing_fact: null, ...change }
}

export const INTIMATE_IMAGE_DESCRIPTION =
  'Our app takes a photo of a person a user uploads and returns an edited picture that shows that person undressed. We built it and sell it under our own name.'

const ART_5_1_BA: Citation = {
  provision_id: 'art:5:1:ba',
  document_id: 'ai-act-consolidated',
  law_version: 'amended',
  language: 'en',
  changed_by_omnibus: true,
  quote:
    'the placing on the market, the putting into service or the use of an AI system that generates or manipulates realistic images, videos, audio or similar material of an identifiable natural person’s intimate parts, or of an identifiable natural person engaged in sexually explicit activities, without that person’s freely-given, specific, informed, unambiguous and explicit consent for that generation or manipulation',
}

const ART_50_2: Citation = {
  provision_id: 'art:50:2',
  document_id: 'ai-act',
  law_version: 'original',
  language: 'en',
  quote:
    'Providers of AI systems, including general-purpose AI systems, generating synthetic audio, image, video or text content, shall ensure that the outputs of the AI system are marked in a machine-readable format and detectable as artificially generated or manipulated.',
}

/** Under the amended text the app is banned by Art. 5(1)(ba), which the Omnibus added. */
export function intimateImageAmended(): ClassificationResult {
  const base = decidedHighRisk()
  return {
    ...base,
    risk_class: 'prohibited',
    role: 'provider',
    annex_point: null,
    transparency_duties: [],
    obligations: [],
    steps: [
      step(base, 'scope', { decision: 'In scope: an AI system placed on the Union market.' }),
      step(base, 'prohibited', {
        decision:
          "Banned under Art. 5(1)(ba): it generates realistic images of an identifiable person's intimate parts without that person's consent.",
        citations: [ART_5_1_BA],
      }),
    ],
  }
}

/** The same app under the original text: no Art. 5(1)(ba), so no ban; its outputs are synthetic
 *  images, so the Art. 50(2) marking duty applies (limited risk). */
export function intimateImageOriginal(): ClassificationResult {
  const base = decidedHighRisk()
  return underOriginal({
    ...base,
    risk_class: 'limited_risk',
    role: 'provider',
    annex_point: null,
    legal_review: null,
    transparency_duties: ['art:50:2'],
    steps: [
      step(base, 'scope', { decision: 'In scope: an AI system placed on the Union market.' }),
      step(base, 'prohibited', { decision: 'No prohibited practice under Art. 5 matches.' }),
      step(base, 'high_risk', {
        decision: 'Not high-risk: no Annex III use and no Annex I product.',
        citations: [],
      }),
      step(base, 'transparency', {
        decision:
          'Art. 50(2) applies: the app generates synthetic images, so its outputs must be marked as artificially generated.',
        citations: [ART_50_2],
      }),
      step(base, 'role_obligations', {
        decision:
          'Role: provider. Duties not modelled for the original text: the obligations table covers only the amended text, so no duties are listed.',
      }),
    ],
  })
}

export const PRESS_GUARD_DESCRIPTION =
  'We make hydraulic presses. Our camera system watches the danger zone and stops the press when a hand comes too close. It is sold as part of the machine under our name.'

const ANNEX_I_B_21: Citation = {
  provision_id: 'annex:I:B:21',
  document_id: 'ai-act-consolidated',
  law_version: 'amended',
  language: 'en',
  changed_by_omnibus: true,
  quote:
    'Regulation (EU) 2023/1230 of the European Parliament and of the Council of 14 June 2023 on machinery and repealing Directive 2006/42/EC of the European Parliament and of the Council and Council Directive 73/361/EEC',
}

const ART_2_2: Citation = {
  provision_id: 'art:2:2',
  document_id: 'ai-act-consolidated',
  law_version: 'amended',
  language: 'en',
  changed_by_omnibus: true,
  quote:
    'For AI systems classified as high-risk AI systems in accordance with Article 6(1) related to products covered by the Union harmonisation legislation listed in Section B of Annex I, only Article 6(1), Article 60a and Articles 102 to 112 shall apply.',
}

const ANNEX_I_A_1_ORIGINAL: Citation = {
  provision_id: 'annex:I:A:1',
  document_id: 'ai-act',
  law_version: 'original',
  language: 'en',
  quote:
    'Directive 2006/42/EC of the European Parliament and of the Council of 17 May 2006 on machinery, and amending Directive 95/16/EC',
}

/** Under the amended text the guard is machinery in Annex I Section B (point 21): high-risk, but
 *  Art. 2(2) leaves it no AI Act duties. */
export function pressGuardAmended(): ClassificationResult {
  const base = decidedHighRisk()
  return {
    ...base,
    role: 'provider',
    annex_point: 'annex:I:B:21',
    obligations: [],
    steps: base.steps.map((candidate) => {
      if (candidate.step === 'high_risk') {
        return step(base, 'high_risk', {
          decision:
            'High-risk under Art. 6(1): a safety component of machinery (Annex I Section B point 21) that needs a third-party conformity assessment. Art. 2(2): only Art. 6(1), Art. 60a and Art. 102 to 112 apply.',
          citations: [ANNEX_I_B_21, ART_2_2],
        })
      }
      if (candidate.step === 'role_obligations') {
        return step(base, 'role_obligations', {
          decision: 'Role: provider. No AI Act duties: Art. 2(2) applies to Annex I Section B.',
        })
      }
      return { ...candidate, status: 'decided' as const, missing_fact: null }
    }),
  }
}

/** Under the original text machinery is Annex I Section A point 1: high-risk with the AI Act's
 *  own duties, from 2 August 2027 (Art. 113(c)). */
export function pressGuardOriginal(): ClassificationResult {
  const amended = pressGuardAmended()
  return underOriginal({
    ...amended,
    annex_point: 'annex:I:A:1',
    steps: amended.steps.map((candidate) => {
      if (candidate.step === 'high_risk') {
        return {
          ...candidate,
          decision:
            'High-risk under Art. 6(1): a safety component of machinery (Annex I Section A point 1) that needs a third-party conformity assessment.',
          citations: [ANNEX_I_A_1_ORIGINAL],
        }
      }
      if (candidate.step === 'role_obligations') {
        return {
          ...candidate,
          decision:
            'Role: provider. Duties not modelled for the original text: the obligations table covers only the amended text, so no duties are listed.',
        }
      }
      return candidate
    }),
  })
}
