import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'

import { ErrorView } from '@/components/ErrorView'
import { SiteFrame } from '@/components/SiteFrame'

export type RouterContext = { queryClient: QueryClient }

// Each frame is a layout route: _site (the public pages) and app (the app screens). An error or
// an unknown address shows on the site frame.
export const Route = createRootRouteWithContext<RouterContext>()({
  component: Outlet,
  errorComponent: () => (
    <SiteFrame>
      <ErrorView />
    </SiteFrame>
  ),
  notFoundComponent: () => (
    <SiteFrame>
      <ErrorView isNotFound />
    </SiteFrame>
  ),
})
