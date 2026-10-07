import { z } from 'zod'

import type { ClassificationResult } from '@/api'

// A result as the database keeps it (classifications.result). The browser wrote it, or an import
// did (P3), so it is untrusted: it is checked here before any screen reads it, and a row that
// fails the check is shown as unreadable, never as a class. The check covers every field the
// inventory and the result screens branch on; the texts inside are rendered as plain text.

const RISK_CLASSES = [
  'out_of_scope',
  'prohibited',
  'high_risk',
  'limited_risk',
  'minimal_risk',
] as const
const STATUSES = ['decided', 'needs_more_information', 'legally_ambiguous'] as const
const ROLES = ['provider', 'deployer', 'importer', 'distributor'] as const
const STEP_NAMES = ['scope', 'prohibited', 'high_risk', 'transparency', 'role_obligations'] as const

const CitationSchema = z.looseObject({
  provision_id: z.string(),
  language: z.enum(['en', 'de']),
  quote: z.string(),
})

const FactSchema = z.looseObject({
  text: z.string(),
  evidence: z.enum(['stated', 'inferred', 'assumed']),
})

const QuestionSchema = z.looseObject({ id: z.string(), text: z.string() })

const ReadingSchema = z.looseObject({
  explanation: z.string(),
  citation: CitationSchema.nullish(),
})

const StepSchema = z.looseObject({
  step: z.enum(STEP_NAMES),
  decision: z.string(),
  status: z.enum(STATUSES).optional(),
  citations: z.array(CitationSchema).optional(),
  facts_used: z.array(FactSchema).optional(),
  missing_fact: QuestionSchema.nullish(),
  open_question: z
    .looseObject({ question: z.string(), readings: z.tuple([ReadingSchema, ReadingSchema]) })
    .nullish(),
})

// The dating fields only: the texts (duty, labels) came with later stories (C9), and a result
// stored before them still loads; the screens render whatever text is there as plain text.
const ObligationSchema = z.looseObject({
  article: z.string(),
  applies_from: z.iso.date(),
  high_risk_route: z.enum(['annex_iii', 'annex_i']).nullish(),
  legacy: z.enum(['legacy_unchanged', 'legacy_public_authority']).nullish(),
  is_informational: z.boolean().optional(),
})

const StoredResultSchema = z.looseObject({
  risk_class: z.enum(RISK_CLASSES),
  status: z.enum(STATUSES),
  law_version: z.enum(['original', 'amended']),
  law_text: z.looseObject({ version_date: z.iso.date() }).optional(),
  as_of: z.iso.date(),
  disclaimer: z.string(),
  facts: z.array(FactSchema),
  steps: z.array(StepSchema),
  role: z.enum(ROLES).nullish(),
  also_role: z.enum(ROLES).nullish(),
  annex_point: z.string().nullish(),
  transparency_duties: z.array(z.string()).optional(),
  deciding_facts: z.array(FactSchema).optional(),
  obligations: z.array(ObligationSchema).optional(),
  follow_up_questions: z.array(QuestionSchema).optional(),
})

/** A stored result, or null when it isn't one Klar can show. */
export function parseStoredResult(value: unknown): ClassificationResult | null {
  const parsed = StoredResultSchema.safeParse(value)
  // The schema checks the fields the screens rely on and keeps the rest as stored; the result
  // type describes the rest as the engine wrote it.
  return parsed.success ? (parsed.data as ClassificationResult) : null
}
