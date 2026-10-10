import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { listDocuments, type DocumentInfo } from '@/api'
import type { Language } from '@/i18n'

export class DocumentsLookupError extends Error {
  constructor(status: number | null) {
    super(`documents lookup failed: ${String(status)}`)
    this.name = 'DocumentsLookupError'
  }
}

/** The legal texts the corpus holds in `language` (`GET /documents`): their titles, kinds and
 *  status, for "Answers draw on". They change only when the corpus is reloaded. */
export function useCorpusDocuments(language: Language): UseQueryResult<DocumentInfo[]> {
  return useQuery({
    queryKey: ['corpus-documents', language] as const,
    queryFn: async (): Promise<DocumentInfo[]> => {
      const { data, response } = await listDocuments({ query: { language } })
      if (!response?.ok || !data) throw new DocumentsLookupError(response?.status ?? null)
      return data.documents
    },
    staleTime: Infinity,
  })
}
