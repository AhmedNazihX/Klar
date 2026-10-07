import type { QueryClient } from '@tanstack/react-query'

import type { CheckedDraft } from '@/api'
import type { ClassificationRun } from '@/features/classify/classification-store'

/**
 * The tools this session has a result for (the Classify screen keeps each finished run in the
 * query cache, P5). P6 stores runs in Supabase and loads them into the same cache entries.
 */
export function sessionTools(queryClient: QueryClient): ClassificationRun[] {
  return queryClient
    .getQueriesData<ClassificationRun | null>({ queryKey: ['classification-run'] })
    .flatMap(([, run]) => (run ? [run] : []))
}

/** One tool and its drafted documents, once drafted. */
export type ToolDocuments = {
  tool: ClassificationRun
  drafts: readonly CheckedDraft[] | undefined
}

export type SelectedDocument = { tool: ClassificationRun; draft: CheckedDraft }

/**
 * The document on show. A document is keyed by its tool and its template id (P5's duty links
 * carry the template only, `?tool=` adds the tool). Without a tool, the first tool that has the
 * template; without a template, the tool's first document. Null while nothing matches.
 */
export function selectDocument(
  entries: readonly ToolDocuments[],
  documentId: string | undefined,
  toolId: string | undefined,
): SelectedDocument | null {
  const candidates = toolId ? entries.filter((entry) => entry.tool.toolId === toolId) : entries
  for (const { tool, drafts } of candidates) {
    const draft = documentId
      ? drafts?.find((item) => item.document.template === documentId)
      : drafts?.[0]
    if (draft) return { tool, draft }
  }
  return null
}
