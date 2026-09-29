import { createClient, type SupabaseClient } from '@supabase/supabase-js'

import { env, type AppEnv } from './env'

/**
 * The browser Supabase client, or `null` when the Supabase variables are not set (tests, a build
 * without a backend). supabase-js keeps the anonymous session in localStorage, which is accepted
 * for the MVP because the session holds no credentials (frontend-security rule, INIT › Storage).
 */
export function createSupabase(config: AppEnv['supabase']): SupabaseClient | null {
  if (!config) return null
  return createClient(config.url, config.anonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  })
}

export const supabase: SupabaseClient | null = createSupabase(env.supabase)
