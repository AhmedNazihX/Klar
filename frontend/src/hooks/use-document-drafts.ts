import {
  queryOptions,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query'

import {
  draftDocument,
  exportDocument,
  listResultDocuments,
  type CheckedDraft,
  type ClassificationResult,
  type ExportRequest,
  type ListedDocument,
  type SizeClass,
} from '@/api'
import type { AnswersByTemplate } from '@/features/documents/interview-answers'
import {
  documentDraftsKey,
  documentListKey,
  interviewAnswersKey,
} from '@/features/documents/query-keys'
import type { Language } from '@/i18n'

/** A tool the Documents screen drafts for: its id in the inventory (`systems.id`), its name
 *  (null when the user gave none) and its latest result. */
export type DocumentTool = {
  toolId: string
  name: string | null
  result: ClassificationResult
}

/** Why the API refused a document request, by its HTTP status: the request was too large or the
 *  document too long for a file (413), the draft failed its checks (409), Klar is busy (429,
 *  503), the file took too long to make (504), or anything else (no response at all, offline,
 *  included). */
export type DocumentFailure = 'too-large' | 'checks-failed' | 'busy' | 'timed-out' | 'failed'

const FAILURES: Readonly<Record<number, DocumentFailure>> = {
  409: 'checks-failed',
  413: 'too-large',
  429: 'busy',
  503: 'busy',
  504: 'timed-out',
}

export class DocumentRequestError extends Error {
  readonly failure: DocumentFailure

  constructor(status: number | null) {
    super(`document request failed: ${String(status)}`)
    this.name = 'DocumentRequestError'
    this.failure = (status !== null && FAILURES[status]) || 'failed'
  }
}

/** The failure an error stands for: a refused request names its own, anything else 'failed'. */
export function documentFailure(error: unknown): DocumentFailure {
  return error instanceof DocumentRequestError ? error.failure : 'failed'
}

/** The documents a tool's result calls for, each with its interview, in `language`. A result
 *  doesn't change, so the list is asked for once. */
export function documentListOptions(tool: DocumentTool, language: Language) {
  return queryOptions({
    queryKey: [...documentListKey(tool.toolId), language] as const,
    queryFn: async (): Promise<readonly ListedDocument[]> => {
      const { data, response } = await listResultDocuments({
        body: { result: tool.result, language },
      })
      if (!response?.ok || !data) throw new DocumentRequestError(response?.status ?? null)
      return data.documents
    },
    staleTime: Infinity,
    retry: false,
  })
}

/** Every listed tool's documents, in order. */
export function useDocumentLists(
  tools: readonly DocumentTool[],
  language: Language,
): UseQueryResult<readonly ListedDocument[]>[] {
  return useQueries({ queries: tools.map((tool) => documentListOptions(tool, language)) })
}

/** What one document's draft is made from: the tool, the template, the language, the company's
 *  size class (null without a profile), and whether the tool's answers are loaded. */
export type DraftInputs = {
  tool: DocumentTool
  template: string
  hasAnswers: boolean
  language: Language
  sizeClass: SizeClass | null
}

/** One document, drafted and checked by the API from the tool's result and the answers in the
 *  cache for that document only, so no request carries another document's answers. Saving an
 *  answer refreshes the tool's drafts (`documentDraftsKey`), and the draft on show stays until
 *  the new one arrives. Waits for the answers. */
export function documentDraftOptions(
  queryClient: QueryClient,
  { tool, template, hasAnswers, language, sizeClass }: DraftInputs,
) {
  return queryOptions({
    queryKey: [...documentDraftsKey(tool.toolId), template, language, sizeClass] as const,
    queryFn: async (): Promise<CheckedDraft> => {
      const answers = queryClient.getQueryData<AnswersByTemplate>(interviewAnswersKey(tool.toolId))
      const { data, response } = await draftDocument({
        body: {
          result: tool.result,
          template,
          language,
          size_class: sizeClass,
          answers: answers?.[template] ?? {},
        },
      })
      if (!response?.ok || !data) throw new DocumentRequestError(response?.status ?? null)
      return data
    },
    enabled: hasAnswers,
    staleTime: Infinity,
    retry: false,
    placeholderData: (previous) => previous,
  })
}

/** The draft of the document on show. */
export function useDocumentDraft(inputs: DraftInputs): UseQueryResult<CheckedDraft> {
  const queryClient = useQueryClient()
  return useQuery(documentDraftOptions(queryClient, inputs))
}

/** The file's name: the template id and the format's extension. */
export function exportFileName(request: ExportRequest): string {
  return `${request.template}.${request.format}`
}

async function fetchFile(request: ExportRequest): Promise<Blob> {
  const { data, response } = await exportDocument({ body: request, parseAs: 'blob' })
  // No response at all (offline) leaves `response` unset.
  if (!response?.ok || !(data instanceof Blob)) {
    throw new DocumentRequestError(response?.status ?? null)
  }
  return data
}

/** Hands a file to the browser to save. */
function saveFile(file: Blob, name: string): void {
  const url = URL.createObjectURL(file)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

/** Downloads one document as .docx or PDF, made by the API from the posted result and answers. */
export function useExportDocument(): UseMutationResult<void, Error, ExportRequest> {
  return useMutation({
    retry: false,
    mutationFn: async (request: ExportRequest) => {
      saveFile(await fetchFile(request), exportFileName(request))
    },
  })
}
