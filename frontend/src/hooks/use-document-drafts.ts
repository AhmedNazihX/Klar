import {
  queryOptions,
  useMutation,
  useQueries,
  useQueryClient,
  type QueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query'

import {
  draftDocuments,
  exportDocument,
  type CheckedDraft,
  type ExportRequest,
  type SizeClass,
} from '@/api'
import type { ClassificationRun } from '@/features/classify/classification-store'
import type { AnswersByTemplate } from '@/features/documents/interview-answers'
import { documentDraftsKey, interviewAnswersKey } from '@/features/documents/query-keys'
import type { Language } from '@/i18n'

/** What one tool's drafts are made from: its result, the language and the company's size class
 *  (null without a profile), and the answers stored for it, once they are loaded. */
export type DraftInputs = {
  tool: ClassificationRun
  hasAnswers: boolean
  language: Language
  sizeClass: SizeClass | null
}

/** One tool's documents, drafted and checked by the API from its result and the answers in the
 *  cache. Saving an answer refreshes them (`documentDraftsKey`), and the drafts on show stay
 *  until the new ones arrive. Waits for the answers. */
export function documentDraftsOptions(
  queryClient: QueryClient,
  { tool, hasAnswers, language, sizeClass }: DraftInputs,
) {
  return queryOptions({
    queryKey: [...documentDraftsKey(tool.toolId), language, sizeClass] as const,
    queryFn: async (): Promise<readonly CheckedDraft[]> => {
      const answers = queryClient.getQueryData<AnswersByTemplate>(interviewAnswersKey(tool.toolId))
      const { data } = await draftDocuments({
        body: { result: tool.result, language, size_class: sizeClass, answers: answers ?? {} },
        throwOnError: true,
      })
      return data.documents
    },
    enabled: hasAnswers,
    staleTime: Infinity,
    retry: false,
  })
}

/** Every listed tool's drafts, in order. */
export function useDocumentDrafts(
  inputs: readonly DraftInputs[],
): UseQueryResult<readonly CheckedDraft[]>[] {
  const queryClient = useQueryClient()
  return useQueries({ queries: inputs.map((input) => documentDraftsOptions(queryClient, input)) })
}

/** Why a file couldn't be made: the draft failed its checks (409), or anything else. */
export class ExportFileError extends Error {
  readonly isChecksFailed: boolean

  constructor(status: number | null) {
    super(`export failed: ${String(status)}`)
    this.name = 'ExportFileError'
    this.isChecksFailed = status === CONFLICT
  }
}

const CONFLICT = 409

/** The file's name: the template id and the format's extension. */
export function exportFileName(request: ExportRequest): string {
  return `${request.template}.${request.format}`
}

async function fetchFile(request: ExportRequest): Promise<Blob> {
  const { data, response } = await exportDocument({ body: request, parseAs: 'blob' })
  // No response at all (offline) leaves `response` unset.
  if (!response?.ok || !(data instanceof Blob)) throw new ExportFileError(response?.status ?? null)
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
