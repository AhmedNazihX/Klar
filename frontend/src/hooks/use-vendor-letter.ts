import { queryOptions, useQuery, type UseQueryResult } from '@tanstack/react-query'

import { draftVendorLetter, type ClassificationResult, type VendorLetter } from '@/api'
import type { Language } from '@/i18n'

export class VendorLetterError extends Error {
  constructor(status: number | null) {
    super(`vendor letter failed: ${String(status)}`)
    this.name = 'VendorLetterError'
  }
}

/** The answers the letter can take without an interview: the tool's name, when the user gave it
 *  one (`tool_name`, P28's question key). The recipient and the sender stay "To fill in". */
export function letterAnswers(toolName: string | null): Record<string, string> {
  const name = toolName?.trim()
  return name ? { tool_name: name } : {}
}

/** The vendor letter the result calls for (`POST /documents/vendor-letter`, P28), drafted by the
 *  API in `language` with its automatic checks; no model is involved. The key holds the result
 *  itself (TanStack Query hashes it, keys sorted), so a later run of the tool, even one on the
 *  same day, asks for its own letter and never gets an older one, however long a letter stays
 *  cached. Nothing is kept once the dialog closes. */
export function vendorLetterOptions(
  toolId: string,
  toolName: string | null,
  result: ClassificationResult,
  language: Language,
) {
  const answers = letterAnswers(toolName)
  return queryOptions({
    queryKey: ['vendor-letter', toolId, language, answers, result] as const,
    queryFn: async (): Promise<VendorLetter> => {
      const { data, response } = await draftVendorLetter({ body: { result, language, answers } })
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
  toolName: string | null,
  result: ClassificationResult,
  language: Language,
): UseQueryResult<VendorLetter> {
  return useQuery(vendorLetterOptions(toolId, toolName, result, language))
}
