import { createFileRoute, redirect } from '@tanstack/react-router'

import { userDataOverviewOptions } from '@/hooks/use-user-data-overview'
import { supabase } from '@/lib/supabase'

/**
 * Where the app's start goes: Welcome while the user has neither a company profile nor a tool
 * (and when nothing can be saved, without Supabase), otherwise the inventory. If the user's data
 * can't be read, the inventory: a returning user isn't sent back to the first visit.
 */
async function startPath(
  queryClient: Parameters<typeof userDataOverviewOptions>[0],
): Promise<'/app/welcome' | '/app/inventory'> {
  if (!supabase) return '/app/welcome'
  try {
    const overview = await queryClient.query(userDataOverviewOptions(queryClient, supabase))
    return overview.profile === null && overview.toolCount === 0 ? '/app/welcome' : '/app/inventory'
  } catch {
    return '/app/inventory'
  }
}

export const Route = createFileRoute('/app/')({
  beforeLoad: async ({ search, context }) => {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- the router's redirect is thrown
    throw redirect({ to: await startPath(context.queryClient), search })
  },
})
