// Classification fixtures for the Classify and result screens (P5), typed from the generated client.
//
// WORKED_EXAMPLE_EVENTS is recorded: the SSE events `POST /classify` streamed for INIT's worked
// example, replayed from E10's recorded engine run (backend/tests/api/test_classify_replay.py's
// cassette, no model or network call) and dumped as JSON; dumped again after C9, whose duties
// carry their short labels, German texts, group and document. Its result needs more information:
// the scope check asked the Art. 3(1) inference question (E10: a valid result for the example).
//
// The variants below are hand-made from that recorded result, changing only the fields a layout
// depends on (decision 026 items 17, 18, 19, 24), because no full recorded run exists for them.
// Their engine texts follow the engine's own templates; they are fixtures, not engine output.
import { http, HttpResponse } from 'msw'

import type {
  Citation,
  ClassificationResult,
  ClassifyResponse,
  FollowUpQuestion,
  Obligation,
  StepResult,
} from '@/api'
import { env } from '@/lib/env'

import recordedEvents from './fixtures/worked-example.events.json'

export const CLASSIFY_URL = `${env.apiUrl}/classify`

export const WORKED_EXAMPLE_DESCRIPTION =
  "We're a 40-person logistics company. We use a tool that reads incoming job applications, scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't change it."

export const WORKED_EXAMPLE_EVENTS = recordedEvents as unknown as readonly ClassifyResponse[]

function recordedResult(): ClassificationResult {
  const last = WORKED_EXAMPLE_EVENTS.at(-1)
  if (last?.event !== 'result') throw new Error('The recorded stream must end with its result.')
  return last.result
}

/** INIT's worked example as recorded: High-risk, Annex III 4(a), deployer, one fact assumed. */
export const WORKED_EXAMPLE: ClassificationResult = recordedResult()

function withSteps(
  result: ClassificationResult,
  change: (step: StepResult) => StepResult,
): StepResult[] {
  return result.steps.map(change)
}

/** The worked example with the inference question answered: decided. */
export function decidedHighRisk(): ClassificationResult {
  return {
    ...WORKED_EXAMPLE,
    status: 'decided',
    follow_up_questions: [],
    steps: withSteps(WORKED_EXAMPLE, (step) =>
      step.step === 'scope'
        ? {
            ...step,
            status: 'decided',
            missing_fact: null,
            decision: 'In scope: an AI system used in the Union.',
          }
        : step,
    ),
  }
}

/** The person-review question of a prohibited check the provider refused, as the engine asks it
 *  under the original text (prohibited_texts.PERSON_REVIEW_ORIGINAL). */
export const PERSON_REVIEW: FollowUpQuestion = {
  id: 'person_review_original',
  text: 'Please have a person review the description: does the system fall under a practice Art. 5(1) prohibits?',
  about: 'art:5:1',
  hint: null,
  options: [],
}

/** The worked example with its prohibited check refused by the model provider's content filter
 *  (decision 030): every step, no class and nothing a class brings. */
export function providerRefused(): ClassificationResult {
  return {
    ...WORKED_EXAMPLE,
    risk_class: null,
    status: 'needs_more_information',
    annex_point: null,
    transparency_duties: [],
    obligations: [],
    legal_review: null,
    not_assessed: ['prohibited'],
    follow_up_questions: [...(WORKED_EXAMPLE.follow_up_questions ?? []), PERSON_REVIEW],
    steps: withSteps(WORKED_EXAMPLE, (step) =>
      step.step === 'prohibited'
        ? {
            ...step,
            status: 'needs_more_information',
            decision:
              "The model provider's content filter blocked this description, so it could not be assessed automatically. No risk class is given: a person must review the description.",
            missing_fact: PERSON_REVIEW,
            error: 'provider_refusal',
          }
        : step,
    ),
  }
}

/** The worked example as decision 029 stored it with its transparency check refused, before
 *  decision 030: the refused check listed in `not_assessed`, the class and its duties kept. */
export function storedBeforeDecision030(): ClassificationResult {
  return {
    ...WORKED_EXAMPLE,
    status: 'needs_more_information',
    not_assessed: ['transparency'],
    steps: withSteps(WORKED_EXAMPLE, (step) =>
      step.step === 'transparency'
        ? {
            ...step,
            status: 'needs_more_information',
            missing_fact: PERSON_REVIEW,
            error: 'provider_refusal',
          }
        : step,
    ),
  }
}

// The duties below carry the texts of C9's obligations table (supabase/seed/obligations.yaml).
const AI_LITERACY_PROVIDER: Obligation = {
  key: 'ai-literacy',
  duty: 'Take measures to support the AI literacy of staff and others who operate or use the system on your behalf.',
  duty_de:
    'Maßnahmen ergreifen, um die KI-Kompetenz Ihres Personals und anderer Personen zu unterstützen, die in Ihrem Auftrag mit dem Betrieb und der Nutzung des Systems befasst sind.',
  label_en: 'Help the people who run or use it build their AI literacy',
  label_de: 'Die KI-Kompetenz der Personen fördern, die es betreiben oder nutzen',
  group: 'after_launch',
  article: 'art:4:1',
  applies_from: '2025-02-02',
}

const IMPORTER_CHECK: Obligation = {
  key: 'hr-importer-verify',
  duty: 'Before placing the system on the market, verify that the provider carried out the conformity assessment, drew up the technical documentation, affixed the CE marking with the declaration of conformity and instructions, and appointed an authorised representative.',
  duty_de:
    'Vor dem Inverkehrbringen überprüfen, ob der Anbieter das Konformitätsbewertungsverfahren durchgeführt und die technische Dokumentation erstellt hat, ob das System mit der CE- Kennzeichnung versehen ist und ihm die EU-Konformitätserklärung und die Betriebsanleitung beigefügt sind und ob der Anbieter einen Bevollmächtigten benannt hat.',
  label_en: 'Before you bring it to market, check the provider did its conformity work',
  label_de:
    'Vor dem Inverkehrbringen prüfen, ob der Anbieter seine Konformitätspflichten erfüllt hat',
  article: 'art:23:1',
  applies_from: '2027-12-02',
  high_risk_route: 'annex_iii',
}

const DISTRIBUTOR_CHECK: Obligation = {
  key: 'hr-distributor-verify',
  duty: 'Before making the system available, verify the CE marking, the declaration of conformity and instructions for use, and that the provider and importer put their names and contact details on it.',
  duty_de:
    'Vor der Bereitstellung auf dem Markt überprüfen, ob das System mit der CE-Kennzeichnung versehen ist, ob ihm die EU-Konformitätserklärung und die Betriebsanleitung beigefügt sind und ob Anbieter und Einführer ihren Namen und ihre Kontaktanschrift angegeben haben.',
  label_en: 'Before you supply it, check its CE marking, declaration and instructions',
  label_de: 'Vor der Bereitstellung CE-Kennzeichnung, Erklärung und Betriebsanleitung prüfen',
  article: 'art:24:1',
  applies_from: '2027-12-02',
  high_risk_route: 'annex_iii',
}

/** Decision 026 item 17: an importer or a distributor gets the deployer-style result. */
export function withRole(role: 'importer' | 'distributor'): ClassificationResult {
  const duty = role === 'importer' ? IMPORTER_CHECK : DISTRIBUTOR_CHECK
  return { ...decidedHighRisk(), role, obligations: [duty] }
}

const RISK_MANAGEMENT: Obligation = {
  key: 'hr-provider-risk-management',
  duty: "Establish, implement, document and maintain a risk management system, run as a continuous process over the system's whole lifecycle.",
  duty_de:
    'Ein Risikomanagementsystem einrichten, anwenden, dokumentieren und aufrechterhalten, als kontinuierlichen Prozess über den gesamten Lebenszyklus des Systems.',
  label_en: 'Run a risk management system for its whole life',
  label_de: 'Ein Risikomanagementsystem über den gesamten Lebenszyklus betreiben',
  group: 'build',
  document: 'art_9_risk_management',
  article: 'art:9',
  applies_from: '2027-12-02',
  high_risk_route: 'annex_iii',
}

const TECHNICAL_DOCUMENTATION: Obligation = {
  key: 'hr-provider-technical-documentation',
  duty: 'Draw up the technical documentation (Annex IV) before placing the system on the market, and keep it up to date.',
  duty_de:
    'Die technische Dokumentation (Anhang IV) erstellen, bevor das System in Verkehr gebracht oder in Betrieb genommen wird, und sie auf dem neuesten Stand halten.',
  label_en: 'Write the technical documentation and keep it up to date',
  label_de: 'Die technische Dokumentation erstellen und aktuell halten',
  group: 'prove',
  document: 'annex_iv_technical_documentation',
  article: 'art:11:1',
  applies_from: '2027-12-02',
  high_risk_route: 'annex_iii',
}

/** Decision 026 item 24: duties marked under Art. 111(2) (on the market before the route date,
 *  no significant change since), for a provider, who also gets the per-copy caveat. */
export function legacyMarked(): ClassificationResult {
  const base = decidedHighRisk()
  return {
    ...base,
    role: 'provider',
    obligations: [
      { ...RISK_MANAGEMENT, legacy: 'legacy_unchanged' },
      { ...TECHNICAL_DOCUMENTATION, applies_from: '2030-08-02', legacy: 'legacy_public_authority' },
    ],
  }
}

/** Item 24 for a provider of a system for public authorities: Art. 111(2) dates every route
 *  duty 2 August 2030, so the result carries no route date of its own. */
export function legacyForPublicAuthorities(): ClassificationResult {
  const base = decidedHighRisk()
  const legacy = { applies_from: '2030-08-02', legacy: 'legacy_public_authority' as const }
  return {
    ...base,
    role: 'provider',
    obligations: [
      AI_LITERACY_PROVIDER,
      { ...RISK_MANAGEMENT, ...legacy },
      { ...TECHNICAL_DOCUMENTATION, ...legacy },
    ],
  }
}

/** Item 24 for a deployer: the same markings on its own duties, without the per-copy caveat
 *  (Art. 111(2) counts per copy only for a role that supplies the system, decision 022). */
export function legacyMarkedDeployer(): ClassificationResult {
  const base = decidedHighRisk()
  return {
    ...base,
    obligations: (base.obligations ?? []).map((obligation) =>
      obligation.high_risk_route
        ? { ...obligation, legacy: 'legacy_unchanged' as const }
        : obligation,
    ),
  }
}

const ART_50_4: Citation = {
  provision_id: 'art:50:4',
  document_id: 'ai-act-consolidated',
  language: 'en',
  quote:
    'Deployers of an AI system that generates or manipulates image, audio or video content constituting a deep fake, shall disclose that the content has been artificially generated or manipulated',
}

const AI_LITERACY: Obligation = {
  key: 'ai-literacy',
  duty: 'Take measures to support the AI literacy of staff and others who operate or use the system on your behalf.',
  duty_de:
    'Maßnahmen ergreifen, um die KI-Kompetenz Ihres Personals und anderer Personen zu unterstützen, die in Ihrem Auftrag mit dem Betrieb und der Nutzung des Systems befasst sind.',
  label_en: 'Help the people who run or use it build their AI literacy',
  label_de: 'Die KI-Kompetenz der Personen fördern, die es betreiben oder nutzen',
  article: 'art:4:1',
  applies_from: '2025-02-02',
}

const DEEP_FAKE_DISCLOSURE: Obligation = {
  key: 'transparency-deep-fake',
  duty: 'Disclose that deep-fake image, audio or video content, or text published to inform the public on matters of public interest, has been artificially generated or manipulated.',
  duty_de:
    'Offenlegen, dass Deepfake-Bild-, Ton- oder Videoinhalte oder Texte, die veröffentlicht werden, um die Öffentlichkeit über Angelegenheiten von öffentlichem Interesse zu informieren, künstlich erzeugt oder manipuliert wurden.',
  label_en: 'Disclose AI-made content that could pass as real',
  label_de: 'Offenlegen, wenn Inhalte echt wirken, aber KI-erzeugt sind',
  document: 'art_50_4_disclosure',
  article: 'art:50:4',
  applies_from: '2026-08-02',
}

function notHighRisk(result: ClassificationResult): StepResult[] {
  return withSteps(result, (step) =>
    step.step === 'high_risk'
      ? { ...step, decision: 'Not high-risk: no Annex III use and no Annex I product.' }
      : step,
  )
}

/** Decision 026 item 19: limited risk, with the Art. 50 duty and its drafted disclosure (a
 *  deployer's Art. 50(4) duty: C9's table has a disclosure template for 50(3) and 50(4)). */
export function limitedRisk(): ClassificationResult {
  const base = decidedHighRisk()
  const steps = notHighRisk(base).map((step) =>
    step.step === 'transparency'
      ? {
          ...step,
          decision:
            'Art. 50(4) applies: the tool makes product videos that look real, so the deployer must disclose they are AI-generated.',
          citations: [ART_50_4],
        }
      : step,
  )
  return {
    ...base,
    risk_class: 'limited_risk',
    role: 'deployer',
    annex_point: null,
    legal_review: null,
    transparency_duties: ['art:50:4'],
    steps,
    obligations: [AI_LITERACY, DEEP_FAKE_DISCLOSURE],
  }
}

const ART_50_1: Citation = {
  provision_id: 'art:50:1',
  document_id: 'ai-act-consolidated',
  language: 'en',
  quote:
    'Providers shall ensure that AI systems intended to interact directly with natural persons are designed and developed in such a way that the natural persons concerned are informed that they are interacting with an AI system',
}

const CHATBOT_DISCLOSURE: Obligation = {
  key: 'transparency-interaction',
  duty: 'Design the system so that people are informed they are interacting with an AI system, unless that is obvious.',
  duty_de:
    'Das System so konzipieren und entwickeln, dass Personen informiert werden, dass sie mit einem KI-System interagieren, es sei denn, dies ist offensichtlich.',
  label_en: "Tell people they're talking to an AI system",
  label_de: 'Personen darüber informieren, dass sie mit einem KI-System interagieren',
  group: 'build',
  article: 'art:50:1',
  applies_from: '2026-08-02',
}

/** Item 19 for a provider's Art. 50(1) chatbot duty, which has no draft template in C9: the
 *  result states the duty and promises no draft. */
export function limitedRiskProvider(): ClassificationResult {
  const base = decidedHighRisk()
  const steps = notHighRisk(base).map((step) =>
    step.step === 'transparency'
      ? {
          ...step,
          decision:
            'Art. 50(1) applies: people talk to the chatbot directly, so they must be told it is an AI system.',
          citations: [ART_50_1],
        }
      : step,
  )
  return {
    ...base,
    risk_class: 'limited_risk',
    role: 'provider',
    annex_point: null,
    legal_review: null,
    transparency_duties: ['art:50:1'],
    steps,
    obligations: [AI_LITERACY, CHATBOT_DISCLOSURE],
  }
}

/** Decision 026 item 19: minimal risk, with only the general Art. 4 duty. */
export function minimalRisk(): ClassificationResult {
  const base = decidedHighRisk()
  return {
    ...base,
    risk_class: 'minimal_risk',
    annex_point: null,
    legal_review: null,
    steps: notHighRisk(base),
    obligations: [AI_LITERACY],
  }
}

const ART_3_1: Citation = {
  provision_id: 'art:3:1',
  document_id: 'ai-act-consolidated',
  language: 'en',
  quote:
    '‘AI system’ means a machine-based system that is designed to operate with varying levels of autonomy and that may exhibit adaptiveness after deployment, and that, for explicit or implicit objectives, infers, from the input it receives, how to generate outputs',
}

export const OUT_OF_SCOPE_DECISION =
  "Out of scope: the tool only applies fixed rules that people wrote; it doesn't infer how to produce its outputs, so it isn't an AI system (Art. 3(1))."

/** Decision 026 item 19: out of scope, with why and the quote, and no duty list. It carries a
 *  stray duty on purpose: the layout must show no list even then. */
export function outOfScope(): ClassificationResult {
  const scope = WORKED_EXAMPLE.steps.find((step) => step.step === 'scope')
  if (!scope) throw new Error('The recorded result has a scope step.')
  return {
    ...WORKED_EXAMPLE,
    risk_class: 'out_of_scope',
    status: 'decided',
    role: null,
    annex_point: null,
    legal_review: null,
    obligations: [AI_LITERACY],
    follow_up_questions: [],
    steps: [
      {
        ...scope,
        status: 'decided',
        missing_fact: null,
        decision: OUT_OF_SCOPE_DECISION,
        citations: [ART_3_1],
      },
    ],
  }
}

const ART_6_1: Citation = {
  provision_id: 'art:6:1',
  document_id: 'ai-act-consolidated',
  language: 'en',
  quote:
    'that AI system shall be considered to be high-risk where both of the following conditions are fulfilled: (a) the AI system is intended to be used as a safety component of a product, or the AI system is itself a product, covered by the Union harmonisation legislation listed in Annex I; (b) the product whose safety component pursuant to point (a) is the AI system, or the AI system itself as a product, is required to undergo a third-party conformity assessment',
}

const ANNEX_I_A_1: Citation = {
  provision_id: 'annex:I:A:1',
  document_id: 'ai-act-consolidated',
  language: 'en',
  quote:
    'Directive 2006/42/EC of the European Parliament and of the Council of 17 May 2006 on machinery',
}

export const ANNEX_I_QUESTION =
  'Under Directive 2006/42/EC on machinery, must the product undergo a third-party conformity assessment (for example by a notified body) for health and safety before it is placed on the market or put into service?'

/** Decision 026 item 18: an Annex I result waiting on the third-party conformity question. */
export function annexINeedsInfo(): ClassificationResult {
  const base = decidedHighRisk()
  const question = {
    id: 'third_party_assessment',
    text: ANNEX_I_QUESTION,
    about: 'art:6:1:b',
    hint: 'If yes, the AI system is high-risk under Art. 6(1). Art. 6(1)(b)',
    options: ['yes', 'no', 'not_sure'] as const,
    if_yes: {
      risk_class: 'high_risk' as const,
      high_risk_route: 'annex_i' as const,
      provision_id: 'annex:I:A:1',
      duties_from: '2028-08-02',
    },
    citations: [ART_6_1, ANNEX_I_A_1],
  }
  return {
    ...base,
    status: 'needs_more_information',
    annex_point: 'annex:I:A:1',
    role: 'provider',
    follow_up_questions: [{ ...question, options: [...question.options] }],
    steps: withSteps(base, (step) =>
      step.step === 'high_risk'
        ? {
            ...step,
            status: 'needs_more_information',
            decision:
              'Working assumption: high-risk under Art. 6(1), pending an answer on the third-party conformity assessment.',
            missing_fact: { ...question, options: [...question.options] },
            citations: [ART_6_1, ANNEX_I_A_1],
          }
        : step,
    ),
  }
}

export const ANNEX_III_QUESTION =
  'Does the tool rank or filter the applications so that HR decides whom to invite from its list?'

/** Decision 026 item 13 on the Annex III route: a High-risk check waiting on one fact, with what a
 *  yes would mean (E12's `if_yes`) and the recorded Annex III 4(a) quote. */
export function annexIIINeedsInfo(): ClassificationResult {
  const base = decidedHighRisk()
  const recorded = base.steps.find((step) => step.step === 'high_risk')
  if (!recorded) throw new Error('The recorded result has a high-risk step.')
  const question: FollowUpQuestion = {
    id: 'used_for_recruitment',
    text: ANNEX_III_QUESTION,
    about: 'annex:III:4:a',
    options: ['yes', 'no', 'not_sure'],
    if_yes: {
      risk_class: 'high_risk',
      high_risk_route: 'annex_iii',
      provision_id: 'annex:III:4:a',
      duties_from: '2027-12-02',
    },
    citations: recorded.citations ?? [],
  }
  return {
    ...base,
    status: 'needs_more_information',
    follow_up_questions: [question],
    steps: withSteps(base, (step) =>
      step.step === 'high_risk'
        ? { ...step, status: 'needs_more_information', missing_fact: question }
        : step,
    ),
  }
}

/** The SSE body `POST /classify` streams: one `data:` line of JSON per event. */
export function sseBody(events: readonly ClassifyResponse[]): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
}

/** An MSW handler that streams `events` once per request and counts the requests. */
export function classifyHandler(
  events: readonly ClassifyResponse[],
  onRequest?: (body: unknown) => void,
) {
  return http.post(CLASSIFY_URL, async ({ request }) => {
    onRequest?.(await request.json())
    return new HttpResponse(sseBody(events), {
      headers: { 'Content-Type': 'text/event-stream' },
    })
  })
}
