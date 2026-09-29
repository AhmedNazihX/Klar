import { env } from './env'

/**
 * Runtime configuration for the generated API client (openapi-ts.config.ts › runtimeConfigPath).
 * The generated src/api/client.gen.ts calls it once, when the client is created. It is typed
 * structurally because the generated `CreateClientConfig` type exists only after `pnpm gen:api`.
 */
export function createClientConfig<T extends { baseUrl?: unknown }>(
  config: T,
): T & {
  baseUrl: string
} {
  return { ...config, baseUrl: env.apiUrl }
}
