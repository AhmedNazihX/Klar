import { queryOptions, useQuery, type UseQueryResult } from '@tanstack/react-query'

import { getProvision, type ClassificationResult, type Provision } from '@/api'
import type { Language } from '@/i18n'

export class ProvisionLookupError extends Error {
  constructor(status: number | null) {
    super(`provision lookup failed: ${String(status)}`)
    this.name = 'ProvisionLookupError'
  }
}

/** The text of one provision from the corpus (`GET /provisions/{id}`), in `language`, at the
 *  result's law version and, under the amended text, its date (the original text takes none).
 *  A text never changes for its version and date, so it is asked for once. */
export function provisionOptions(
  provisionId: string,
  language: Language,
  result: Pick<ClassificationResult, 'law_version' | 'as_of'>,
) {
  const asOf = result.law_version === 'amended' ? result.as_of : null
  return queryOptions({
    queryKey: ['provision', provisionId, language, result.law_version, asOf] as const,
    queryFn: async (): Promise<Provision> => {
      const { data, response } = await getProvision({
        path: { provision_id: provisionId },
        query: { language, law_version: result.law_version, ...(asOf ? { as_of: asOf } : {}) },
      })
      if (!response?.ok || !data) throw new ProvisionLookupError(response?.status ?? null)
      return data
    },
    staleTime: Infinity,
  })
}

/** One provision's text, as the corpus words it (never the result's copy of it). */
export function useProvision(
  provisionId: string,
  language: Language,
  result: Pick<ClassificationResult, 'law_version' | 'as_of'>,
): UseQueryResult<Provision> {
  return useQuery(provisionOptions(provisionId, language, result))
}
