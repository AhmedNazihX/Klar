// Where the end-to-end run's servers are (story P13). Read by playwright.config.ts, before any
// server starts.
//
// - The e2e Supabase stack (e2e/supabase/config.toml), started beforehand with
//   `supabase start --workdir frontend/e2e` (or `make e2e-db`): its URL and publishable key come
//   from `supabase status`, never from .env.local, so the run can't reach the hosted project.
// - The API in replay mode (backend/tests/e2e/replay_server.py) and the built app (`vite preview`),
//   on ports of their own, so a developer's `make dev` (8000, 5173) keeps running untouched.
import { execFileSync } from 'node:child_process'
import path from 'node:path'

export const API_PORT = 8766
export const WEB_PORT = 4174
export const API_URL = `http://127.0.0.1:${API_PORT}`
export const WEB_URL = `http://127.0.0.1:${WEB_PORT}`

const E2E_WORKDIR = path.resolve(import.meta.dirname)
const LOOPBACK = new Set(['127.0.0.1', 'localhost', '[::1]'])

export type SupabaseStack = { url: string; anonKey: string }

/** The e2e stack's API URL and publishable key. Throws when the stack isn't running, or when its
 *  URL isn't on this machine. */
export function supabaseStack(): SupabaseStack {
  let output: string
  try {
    output = execFileSync('supabase', ['status', '--workdir', E2E_WORKDIR, '-o', 'json'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    })
  } catch {
    throw new Error(
      'The e2e Supabase stack is not running. Start it with `make e2e-db` from the repo root.',
    )
  }
  const status = JSON.parse(output) as Record<string, unknown>
  const url = status.API_URL
  const anonKey = status.PUBLISHABLE_KEY ?? status.ANON_KEY
  if (typeof url !== 'string' || typeof anonKey !== 'string') {
    throw new Error('`supabase status` gave no API URL or publishable key for the e2e stack.')
  }
  if (!LOOPBACK.has(new URL(url).hostname)) {
    throw new Error(`The e2e Supabase stack must be local, not ${new URL(url).hostname}.`)
  }
  return { url, anonKey }
}
