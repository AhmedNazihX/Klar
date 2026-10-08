import type { SupabaseClient } from '@supabase/supabase-js'
import { z } from 'zod'

/** The guided interview's answers, kept by the browser in Supabase under the user's session
 *  (RLS): one row per tool, template and question. */
const TABLE = 'interview_answers'

/** The table's unique key (P19): an upsert names all four columns; `user_id` is the session's. */
export const ANSWER_CONFLICT_KEY = 'system_id,user_id,template,question_key'

/** As `interview_answers.answer` allows (20,000 characters). */
export const MAX_ANSWER_CHARS = 20_000

/** One tool's answers: question key by template id, as the API's `answers` takes them. */
export type AnswersByTemplate = Readonly<Record<string, Readonly<Record<string, string>>>>

export type InterviewAnswer = {
  toolId: string
  template: string
  questionKey: string
  answer: string
}

const AnswerRowSchema = z.object({
  template: z.string().min(1),
  question_key: z.string().min(1),
  answer: z.string(),
})

/** `answers` with one answer set (a new object; `answers` is left as it was). */
export function withAnswer(answers: AnswersByTemplate, saved: InterviewAnswer): AnswersByTemplate {
  return {
    ...answers,
    [saved.template]: { ...answers[saved.template], [saved.questionKey]: saved.answer },
  }
}

/** Every answer the user gave for one tool, by template. */
export async function fetchInterviewAnswers(
  client: SupabaseClient,
  toolId: string,
): Promise<AnswersByTemplate> {
  const { data, error } = await client
    .from(TABLE)
    .select('template, question_key, answer')
    .eq('system_id', toolId)
  if (error) throw error
  const rows = z.array(AnswerRowSchema).parse(data)
  return rows.reduce<AnswersByTemplate>(
    (answers, row) =>
      withAnswer(answers, {
        toolId,
        template: row.template,
        questionKey: row.question_key,
        answer: row.answer,
      }),
    {},
  )
}

/** Saves one answer, replacing the one given before. Throws the database's error (PT507 when
 *  the user's storage is full, decision 027). */
export async function saveInterviewAnswer(
  client: SupabaseClient,
  saved: InterviewAnswer,
): Promise<void> {
  const { error } = await client.from(TABLE).upsert(
    {
      system_id: saved.toolId,
      template: saved.template,
      question_key: saved.questionKey,
      answer: saved.answer,
    },
    { onConflict: ANSWER_CONFLICT_KEY },
  )
  if (error) throw error
}
