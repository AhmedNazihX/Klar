import { QueryClient } from '@tanstack/react-query'

const STALE_TIME_MS = 30_000

/**
 * One QueryClient for the app. Tests make their own, with retries off (src/test/test-utils.tsx).
 * Nothing refetches on reconnect: a read of the user's data needs the anonymous session, so after
 * Delete my data such a background read would start a new session (a new anonymous user) in a
 * tab the visitor isn't using. Reads run again when a screen mounts or after a write.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: STALE_TIME_MS,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
    },
  })
}
