import { QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createTestQueryClient } from '@/test/test-utils'

import { Route as AppRoute } from './app'

// The real /app layout route's options, under a bare root, with one child screen that fails.
function renderFailingScreen() {
  const root = createRootRoute({ component: Outlet })
  const { validateSearch, search, component, errorComponent } = AppRoute.options
  const app = createRoute({
    getParentRoute: () => root,
    path: 'app',
    validateSearch,
    search,
    component,
    errorComponent,
  })
  const failing = createRoute({
    getParentRoute: () => app,
    path: 'broken',
    component: () => {
      throw new Error('screen failed')
    },
  })
  const router = createRouter({
    routeTree: root.addChildren([app.addChildren([failing])]),
    history: createMemoryHistory({ initialEntries: ['/app/broken?law=original'] }),
  })
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('/app error', () => {
  it('shows a failing screen inside the app frame, sidebar and law switch kept', async () => {
    // React logs the caught error; keep the test output clean.
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    renderFailingScreen()

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
    expect(screen.getByRole('navigation', { name: 'App' })).toBeInTheDocument()
    const group = screen.getByRole('group', { name: 'Law version' })
    expect(group.querySelectorAll('button')[1]).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Guidance, not legal advice. Klar is an AI system.')).toBeVisible()
    expect(screen.queryByText('screen failed')).toBeNull()
  })
})
