import { QueryClient } from '@tanstack/react-query'

const STALE_TIME_MS = 30_000

/** One QueryClient for the app. Tests make their own, with retries off (src/test/test-utils.tsx). */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: STALE_TIME_MS, refetchOnWindowFocus: false },
    },
  })
}
