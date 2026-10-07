import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
import type { JSX } from 'react'

import { ErrorView } from '@/components/ErrorView'
import { SiteFrame } from '@/components/SiteFrame'
import { useForgetOnSignOut } from '@/hooks/use-forget-on-sign-out'

export type RouterContext = { queryClient: QueryClient }

/** Every page: a sign-out (Delete my data, here or in another tab) forgets the session's data. */
function RootLayout(): JSX.Element {
  useForgetOnSignOut()
  return <Outlet />
}

// Each frame is a layout route: _site (the public pages) and app (the app screens). An error or
// an unknown address shows on the site frame.
export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
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
