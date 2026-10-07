import { QueryClient } from '@tanstack/react-query'

import { holdsAnonymousSession } from '@/hooks/use-anonymous-session'

const STALE_TIME_MS = 30_000

/**
 * One QueryClient for the app. Tests make their own, with retries off (src/test/test-utils.tsx).
 * On reconnect, stale reads (a failed one included) run again only while this tab holds its
 * anonymous session: a read of the user's data needs the session, so after Delete my data such a
 * background read would start a new session (a new anonymous user) in a tab the visitor isn't
 * using; without a session, reads run again only when a screen mounts or after a write. The
 * session's own query never refetches on reconnect (anonymousSessionOptions).
 */
export function createQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: STALE_TIME_MS,
        refetchOnWindowFocus: false,
        refetchOnReconnect: () => holdsAnonymousSession(queryClient),
      },
    },
  })
  return queryClient
}
