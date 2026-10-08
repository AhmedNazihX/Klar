import type { ListedDocument } from '@/api'
import type { DocumentTool } from '@/hooks/use-document-drafts'
import type { InventoryTool } from '@/lib/inventory'

/** The inventory's tools that have a result Klar can read: the ones with documents to draft.
 *  Their ids are the inventory's (`systems.id`), which interview answers are stored under. */
export function documentTools(tools: readonly InventoryTool[]): DocumentTool[] {
  return tools.flatMap(({ toolId, name, result }) => (result ? [{ toolId, name, result }] : []))
}

/** One tool and the documents its result calls for, once listed. */
export type ToolDocuments = {
  tool: DocumentTool
  documents: readonly ListedDocument[] | undefined
}

export type SelectedDocument = { tool: DocumentTool; document: ListedDocument }

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
  for (const { tool, documents } of candidates) {
    const document = documentId
      ? documents?.find((item) => item.template === documentId)
      : documents?.[0]
    if (document) return { tool, document }
  }
  return null
}
