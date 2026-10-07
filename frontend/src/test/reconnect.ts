// The network dropping and coming back, as TanStack Query sees it, for tests of what a reconnect
// refetches.
import { onlineManager, QueryObserver, type QueryClient } from '@tanstack/react-query'
import { expect, vi } from 'vitest'

const WATCH_KEY = ['test', 'reconnect-watch'] as const

/**
 * Takes the network away and gives it back, then waits until `queryClient` has handled the
 * return and every refetch it started has settled. A query that refetches on every reconnect
 * shows when the return has been handled, as the client handles it a moment later.
 */
export async function reconnect(queryClient: QueryClient): Promise<void> {
  let reads = 0
  const watch = new QueryObserver(queryClient, {
    queryKey: WATCH_KEY,
    queryFn: () => ++reads,
    refetchOnReconnect: 'always',
  })
  const stopWatching = watch.subscribe(() => undefined)
  await vi.waitFor(() => expect(reads).toBe(1))

  onlineManager.setOnline(false)
  onlineManager.setOnline(true)
  await vi.waitFor(() => expect(reads).toBe(2))
  await vi.waitFor(() => expect(queryClient.isFetching()).toBe(0))

  stopWatching()
  queryClient.removeQueries({ queryKey: WATCH_KEY })
}
