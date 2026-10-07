import { queryOptions } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'
import type { Language } from '@/i18n'

/** One finished run: what was asked, and the engine's result. */
export type ClassificationRun = {
  toolId: string
  name: string
  description: string
  language: Language
  result: ClassificationResult
}

/**
 * A run's result, held in the query cache for this session under its tool id. The Classify
 * screen puts it there when the stream ends; nothing loads it from anywhere else yet, so a tool
 * unknown to this session reads as null. P6 stores runs in Supabase and loads them here.
 */
export function classificationRunOptions(toolId: string) {
  return queryOptions({
    queryKey: ['classification-run', toolId] as const,
    queryFn: (): ClassificationRun | null => null,
    staleTime: Infinity,
    gcTime: Infinity,
  })
}

/** What the description form holds. */
export type ClassifyDraft = { name: string; description: string }

const EMPTY_DRAFT: ClassifyDraft = { name: '', description: '' }
let savedDraft: ClassifyDraft = EMPTY_DRAFT

/** The description being worked on, kept for this session: "Save for later" and "Edit
 *  description" bring it back to the form. Never sent anywhere until the user runs the checks. */
export function readDraft(): ClassifyDraft {
  return savedDraft
}

export function saveDraft(draft: ClassifyDraft): void {
  savedDraft = { ...draft }
}

export function clearDraft(): void {
  savedDraft = EMPTY_DRAFT
}
