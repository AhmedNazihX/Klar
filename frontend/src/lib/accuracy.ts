import { z } from 'zod'

import accuracyFile from '@/content/accuracy.json'

// The published accuracy figures (decision 024 addendum): `aiact evaluate site-metrics` (P27) writes
// src/content/accuracy.json from the stored benchmark runs; until then every figure is null and the
// pages show a marked placeholder (components.md › MetricTile: never invent a figure).

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
})

export type AccuracyFigure = z.infer<typeof figureSchema>
export type SiteAccuracy = z.infer<typeof accuracySchema>

/** Checks a figures file; a malformed one is a build error, so it throws with zod's reason. */
export function parseSiteAccuracy(data: unknown): SiteAccuracy {
  return accuracySchema.parse(data)
}

/** The committed figures, checked once when the module loads. */
export const SITE_ACCURACY: SiteAccuracy = parseSiteAccuracy(accuracyFile)
