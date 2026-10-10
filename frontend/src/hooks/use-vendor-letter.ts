import { queryOptions, useQuery, type UseQueryResult } from '@tanstack/react-query'

import { draftVendorLetter, type ClassificationResult, type VendorLetter } from '@/api'
import type { Language } from '@/i18n'

export class VendorLetterError extends Error {
  constructor(status: number | null) {
    super(`vendor letter failed: ${String(status)}`)
    this.name = 'VendorLetterError'
  }
}

/** The vendor letter the result calls for (`POST /documents/vendor-letter`, P28), drafted by the
 *  API in `language` with its automatic checks; no model is involved. The recipient, the tool's
 *  name and the sender stay "To fill in". The letter lives only while it is on show (no cache
 *  after it closes), so a later run of the tool never opens an older letter. */
export function vendorLetterOptions(
  toolId: string,
  result: ClassificationResult,
  language: Language,
) {
  return queryOptions({
    queryKey: ['vendor-letter', toolId, language] as const,
    queryFn: async (): Promise<VendorLetter> => {
      const { data, response } = await draftVendorLetter({
        body: { result, language, answers: {} },
      })
      if (!response?.ok || !data) throw new VendorLetterError(response?.status ?? null)
      return data
    },
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  })
}

export function useVendorLetter(
  toolId: string,
  result: ClassificationResult,
  language: Language,
): UseQueryResult<VendorLetter> {
  return useQuery(vendorLetterOptions(toolId, result, language))
}
