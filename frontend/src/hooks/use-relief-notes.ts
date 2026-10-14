import { useQueries } from '@tanstack/react-query'

import {
  listObligations,
  type ClassificationResult,
  type Obligation,
  type RiskClass,
  type Role,
} from '@/api'

/** A duty's relief notes, in English and German, as the obligations table words them. */
export type ReliefNotes = Pick<Obligation, 'relief_note' | 'relief_note_de'>

/** Each duty's relief notes, by its key in the obligations table. */
export type ReliefTable = Readonly<Record<string, ReliefNotes>>

export class ObligationsLookupError extends Error {
  constructor(status: number | null) {
    super(`obligations lookup failed: ${String(status)}`)
    this.name = 'ObligationsLookupError'
  }
}

async function reliefTableFor(role: Role, riskClass: RiskClass): Promise<ReliefTable> {
  const { data, response } = await listObligations({ query: { role, risk_class: riskClass } })
  if (!response?.ok || !data) throw new ObligationsLookupError(response?.status ?? null)
  return Object.fromEntries(
    data.obligations.flatMap((duty) =>
      duty.key
        ? [[duty.key, { relief_note: duty.relief_note, relief_note_de: duty.relief_note_de }]]
        : [],
    ),
  )
}

/**
 * The relief notes the obligations table gives the duties of `result`'s role, the role it also
 * keeps, and its class (`GET /obligations`, the amended text, the only one the table holds), by
 * duty key, when `isWanted`; the table's, not the stored result's, as in the reports, since a
 * result stored before P11 has no German note and an older one none at all. Undefined when not
 * wanted or while loading; a failed lookup leaves out the notes it would have given.
 */
export function useReliefNotes(
  result: Pick<ClassificationResult, 'role' | 'also_role' | 'risk_class'>,
  isWanted: boolean,
): ReliefTable | undefined {
  const riskClass = result.risk_class
  const roles = [...new Set([result.role, result.also_role])].filter((role) => role != null)
  return useQueries({
    queries:
      riskClass === null
        ? []
        : roles.map((role) => ({
            queryKey: ['relief-notes', role, riskClass] as const,
            queryFn: () => reliefTableFor(role, riskClass),
            enabled: isWanted,
            staleTime: Infinity,
          })),
    combine: (lookups) =>
      lookups.some((lookup) => lookup.isSuccess)
        ? lookups.reduce<ReliefTable>((table, lookup) => ({ ...table, ...lookup.data }), {})
        : undefined,
  })
}
