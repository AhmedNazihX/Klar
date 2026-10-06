import { env } from './env'

/**
 * Never retry a server-sent-events request. The generated SSE client retries any failure
 * forever by default, and every retry of `POST /classify` would start a new paid run (a 422 or
 * 503 would loop). A failed stream ends; the caller decides whether to ask again.
 */
export const SSE_MAX_RETRY_ATTEMPTS = 1

/**
 * Runtime configuration for the generated API client (openapi-ts.config.ts › runtimeConfigPath).
 * The generated src/api/client.gen.ts calls it once, when the client is created. It is typed
 * structurally because the generated `CreateClientConfig` type exists only after `pnpm gen:api`.
 */
export function createClientConfig<T extends { baseUrl?: unknown }>(
  config: T,
): T & {
  baseUrl: string
  sseMaxRetryAttempts: number
} {
  return { ...config, baseUrl: env.apiUrl, sseMaxRetryAttempts: SSE_MAX_RETRY_ATTEMPTS }
}
