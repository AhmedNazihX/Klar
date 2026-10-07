/** The documents screens' search params: `tool`, the tool a document belongs to. */
export type DocumentSearch = { tool?: string }

/** A tool id is at most this long (a UUID is 36 characters). */
const MAX_TOOL_ID_CHARS = 64

/** Keeps a plausible tool id and drops anything else. The key is always set, even to undefined,
 *  so a bogus value can't slip through the router's merge (as with the app's `law`). */
export function validateDocumentSearch(search: Record<string, unknown>): DocumentSearch {
  const { tool } = search
  return {
    tool: typeof tool === 'string' && tool.length <= MAX_TOOL_ID_CHARS ? tool : undefined,
  }
}
