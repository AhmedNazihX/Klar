import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router'
import { render, type RenderResult } from '@testing-library/react'
import i18n from 'i18next'
import type { ReactElement, ReactNode } from 'react'
import { I18nextProvider } from 'react-i18next'

import { createAppRouter } from '@/router'

/** A fresh QueryClient per test, with retries off so failures show at once. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
}

function Providers({ client, children }: { client: QueryClient; children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
    </QueryClientProvider>
  )
}

/** Render one component inside the app's providers and a bare router (for `Link`s). */
export function renderWithProviders(ui: ReactElement): RenderResult {
  const client = createTestQueryClient()
  const router = createRouter({
    routeTree: createRootRoute({ component: () => ui }),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  return render(
    <Providers client={client}>
      <RouterProvider router={router} />
    </Providers>,
  )
}

/** Render the whole app at `path`, with its real routes; `router` tells where it went. */
export function renderRoute(
  path: string,
): RenderResult & { router: ReturnType<typeof createAppRouter> } {
  const client = createTestQueryClient()
  const router = createAppRouter(client, createMemoryHistory({ initialEntries: [path] }))
  const result = render(
    <Providers client={client}>
      <RouterProvider router={router} />
    </Providers>,
  )
  return { ...result, router }
}
