import { z } from 'zod'

import accuracyFile from '@/content/accuracy.json'

// The published accuracy figures (decision 024 addendum): `aiact evaluate site-metrics` (P27) writes
// src/content/accuracy.json from the stored benchmark runs. A null figure shows a marked placeholder
// (components.md › MetricTile: never invent a figure).

/** A number of cases a page sentence states, with the run that counted them. */
const countSchema = z.object({
  count: z.number().int().positive(),
  run_id: z.string().min(1),
})

/** One measured rate, between 0 and 1, with the run it comes from. */
const figureSchema = z.object({
  value: z.number().min(0).max(1),
  run_id: z.string().min(1),
})

const accuracySchema = z.object({
  risk_class_accuracy: figureSchema.nullable(),
  false_low_risk_rate: figureSchema.nullable(),
  citations_exist: figureSchema.nullable(),
  /** Klar and an existing checker on the same cases. */
  head_to_head: z
    .object({
      klar: figureSchema,
      checker: figureSchema,
      checker_name: z.string().min(1),
      cases: z.number().int().positive(),
    })
    .nullable(),
  /** The held-out Commission cases the risk-class accuracy is computed over ("The test set has N"). */
  scored_cases: countSchema.nullable(),
  /** The own cases written for Klar ("plus N cases written for Klar"). */
  own_cases: countSchema.nullable(),
  /** The day the published Commission run started, `YYYY-MM-DD`. */
  run_date: z.iso.date().nullable(),
  /** The final evaluation report: a public URL the Method page links to, or its repository path. */
  report: z.string().min(1).nullable(),
  /** Every run the figures come from, and which runs are published and why. */
  run_ids: z.array(z.string().min(1)),
  note: z.string(),
})

export type AccuracyFigure = z.infer<typeof figureSchema>
export type SiteAccuracy = z.infer<typeof accuracySchema>

/** Checks a figures file; a malformed one is a build error, so it throws with zod's reason. */
export function parseSiteAccuracy(data: unknown): SiteAccuracy {
  return accuracySchema.parse(data)
}

/** The committed figures, checked once when the module loads. */
export const SITE_ACCURACY: SiteAccuracy = parseSiteAccuracy(accuracyFile)
