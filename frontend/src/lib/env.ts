import { z } from 'zod'

// The only settings the frontend reads. Every VITE_* value ships in the public bundle, so none of
// them may be a secret (the anon key is public by design; RLS protects the data).
// The API's default API_PORT (backend/aiact/settings.py); keep the two in step.
const DEFAULT_API_URL = 'http://localhost:8000'

// An unset or blank variable counts as missing.
const optional = <T extends z.ZodType>(schema: T) =>
  z.preprocess((value) => (value === '' ? undefined : value), schema.optional())

const EnvSchema = z.object({
  VITE_API_URL: optional(z.url({ protocol: /^https?$/ })),
  VITE_SUPABASE_URL: optional(z.url({ protocol: /^https?$/ })),
  VITE_SUPABASE_ANON_KEY: optional(z.string().trim().min(1)),
})

export type AppEnv = {
  apiUrl: string
  /** Both set, or neither (then the app runs without a session); one alone is an error. */
  supabase: { url: string; anonKey: string } | null
}

/** Validate the raw `import.meta.env`. Throws with the names of the bad variables. */
export function readEnv(raw: Record<string, unknown>): AppEnv {
  const parsed = EnvSchema.safeParse(raw)
  if (!parsed.success) {
    const names = parsed.error.issues.map((issue) => issue.path.join('.')).join(', ')
    throw new Error(`Invalid frontend environment variables: ${names}. See frontend/.env.example.`)
  }
  const { VITE_API_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY } = parsed.data
  // Half a Supabase configuration is a mistake, not a choice to run without sessions.
  if (Boolean(VITE_SUPABASE_URL) !== Boolean(VITE_SUPABASE_ANON_KEY)) {
    const missing = VITE_SUPABASE_URL ? 'VITE_SUPABASE_ANON_KEY' : 'VITE_SUPABASE_URL'
    throw new Error(
      `${missing} is not set, but the other Supabase variable is. Set both or neither. ` +
        'See frontend/.env.example.',
    )
  }
  return {
    apiUrl: VITE_API_URL ?? DEFAULT_API_URL,
    supabase:
      VITE_SUPABASE_URL && VITE_SUPABASE_ANON_KEY
        ? { url: VITE_SUPABASE_URL, anonKey: VITE_SUPABASE_ANON_KEY }
        : null,
  }
}

export const env: AppEnv = readEnv(import.meta.env)
