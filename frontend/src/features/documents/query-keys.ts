import { userDataKey } from '@/hooks/use-user-data-overview'

// Every key is under the user-data key: a sign-out forgets the answers, the drafts made from
// them and the documents a tool's result calls for with the rest of the user's data.

/** A tool's stored interview answers. */
export function interviewAnswersKey(toolId: string) {
  return [...userDataKey, 'interview-answers', toolId] as const
}

/** The documents a tool's result calls for, in any language. */
export function documentListKey(toolId: string) {
  return [...userDataKey, 'document-list', toolId] as const
}

/** A tool's drafts, of any document, in any language and for any size class: saving an answer
 *  refreshes them all. */
export function documentDraftsKey(toolId: string) {
  return [...userDataKey, 'document-drafts', toolId] as const
}
