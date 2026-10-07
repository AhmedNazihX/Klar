/** A tool's stored interview answers. */
export function interviewAnswersKey(toolId: string) {
  return ['interview-answers', toolId] as const
}

/** A tool's drafts, in any language and for any size class: saving an answer refreshes them all. */
export function documentDraftsKey(toolId: string) {
  return ['document-drafts', toolId] as const
}
