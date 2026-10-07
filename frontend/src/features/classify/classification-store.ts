import { queryOptions } from '@tanstack/react-query'

import type { ClassificationResult } from '@/api'

import type { DescriptionFormValues } from './description-form'

/** One finished run: what was asked, and the engine's result. `name` is as the user typed it,
 *  possibly empty: screens then show "Your tool" in the reader's language. */
export type ClassificationRun = {
  toolId: string
  name: string
  description: string
  result: ClassificationResult
}

/** Every run's query starts with this key, so a sign-out can forget them all. */
export const classificationRunKey = ['classification-run'] as const

/**
 * A run's result, held in the query cache for this session under its tool id. The Classify
 * screen puts it there when the stream ends; nothing loads it from anywhere else yet, so a tool
 * unknown to this session reads as null. P6 stores runs in Supabase and loads them here.
 */
export function classificationRunOptions(toolId: string) {
  return queryOptions({
    queryKey: [...classificationRunKey, toolId] as const,
    queryFn: (): ClassificationRun | null => null,
    staleTime: Infinity,
    gcTime: Infinity,
  })
}

const EMPTY_DRAFT: DescriptionFormValues = { name: '', description: '' }
let savedDraft: DescriptionFormValues = EMPTY_DRAFT

/** The description being worked on, kept for this session: "Save for later" and "Edit
 *  description" bring it back to the form. Never sent anywhere until the user runs the checks. */
export function readDraft(): DescriptionFormValues {
  return savedDraft
}

export function saveDraft(draft: DescriptionFormValues): void {
  savedDraft = { ...draft }
}

export function clearDraft(): void {
  savedDraft = EMPTY_DRAFT
}
