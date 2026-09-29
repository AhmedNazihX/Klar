import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'

import { AppShell } from '@/components/AppShell'
import { ErrorView } from '@/components/ErrorView'

export type RouterContext = { queryClient: QueryClient }

export const Route = createRootRouteWithContext<RouterContext>()({
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
  errorComponent: () => (
    <AppShell>
      <ErrorView />
    </AppShell>
  ),
  notFoundComponent: () => <ErrorView isNotFound />,
})
