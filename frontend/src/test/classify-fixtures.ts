// Classification fixtures for the Classify and result screens (P5), typed from the generated client.
//
// WORKED_EXAMPLE_EVENTS is recorded: the SSE events `POST /classify` streamed for INIT's worked
// example, replayed from E10's recorded engine run (backend/tests/api/test_classify_replay.py's
// cassette, no model or network call) and dumped as JSON. Its result needs more information:
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

/** Decision 026 item 17: an importer or a distributor gets the deployer-style result. */
export function withRole(role: 'importer' | 'distributor'): ClassificationResult {
  const article = role === 'importer' ? 'art:23:1' : 'art:24:1'
  const duty: Obligation = {
    duty:
      role === 'importer'
        ? 'Before placing the system on the market, verify that the provider carried out the conformity assessment and drew up the technical documentation.'
        : 'Before making the system available, verify that it bears the CE marking and comes with the EU declaration of conformity and the instructions for use.',
    article,
    applies_from: '2027-12-02',
    high_risk_route: 'annex_iii',
  }
  return { ...decidedHighRisk(), role, obligations: [duty] }
}

/** Decision 026 item 24: duties marked under Art. 111(2) (on the market before the route date,
 *  no significant change since), for a provider, who also gets the per-copy caveat. */
export function legacyMarked(): ClassificationResult {
  const base = decidedHighRisk()
  return {
    ...base,
    role: 'provider',
    obligations: [
      {
        duty: 'Set up a risk management system that runs through the whole lifecycle of the system.',
        article: 'art:9:1',
        applies_from: '2027-12-02',
        high_risk_route: 'annex_iii',
        legacy: 'legacy_unchanged',
      },
      {
        duty: 'Draw up the technical documentation before the system is placed on the market.',
        article: 'art:11:1',
        applies_from: '2030-08-02',
        high_risk_route: 'annex_iii',
        legacy: 'legacy_public_authority',
      },
    ],
  }
}

const ART_50_1: Citation = {
  provision_id: 'art:50:1',
  document_id: 'ai-act-consolidated',
  language: 'en',
  quote:
    'Providers shall ensure that AI systems intended to interact directly with natural persons are designed and developed in such a way that the natural persons concerned are informed that they are interacting with an AI system',
}

const AI_LITERACY: Obligation = {
  duty: 'Take measures to support the AI literacy of staff and others who operate or use the system on your behalf.',
  article: 'art:4:1',
  applies_from: '2025-02-02',
}

function notHighRisk(result: ClassificationResult): StepResult[] {
  return withSteps(result, (step) =>
    step.step === 'high_risk'
      ? { ...step, decision: 'Not high-risk: no Annex III use and no Annex I product.' }
      : step,
  )
}

/** Decision 026 item 19: limited risk, with the Art. 50 duty and its drafted disclosure. */
export function limitedRisk(): ClassificationResult {
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
    obligations: [
      AI_LITERACY,
      {
        duty: 'Design the system so that people are told they are interacting with an AI system.',
        article: 'art:50:1',
        applies_from: '2026-08-02',
      },
    ],
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

/** Decision 026 item 19: out of scope, with why and the quote, and no duty list. */
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
    obligations: [],
    follow_up_questions: [],
    not_assessed: ['prohibited', 'high_risk', 'transparency', 'role_obligations'],
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
