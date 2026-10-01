import { QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LOAD_MOTION_MS } from '@/hooks/use-load-motion'
import { createTestQueryClient } from '@/test/test-utils'

import { Route as AppRoute } from './app'

// The real /app layout route's options under a bare root, with a working screen and one that
// fails, so the tests can go into the error and out of it again.
function renderApp(path: string) {
  const root = createRootRoute({ component: Outlet })
  const { validateSearch, search, component } = AppRoute.options
  const app = createRoute({
    getParentRoute: () => root,
    path: 'app',
    validateSearch,
    search,
    component,
  })
  const working = createRoute({
    getParentRoute: () => app,
    path: 'working',
    component: () => <h1>Working screen</h1>,
  })
  const failing = createRoute({
    getParentRoute: () => app,
    path: 'broken',
    component: () => {
      throw new Error('screen failed')
    },
  })
  const router = createRouter({
    routeTree: root.addChildren([app.addChildren([working, failing])]),
    history: createMemoryHistory({ initialEntries: [path] }),
  })
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

function frame(): Element | null {
  return document.querySelector('.app-frame')
}

beforeEach(() => {
  // React logs the caught error; keep the test output clean.
  vi.spyOn(console, 'error').mockImplementation(() => undefined)
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('/app error', () => {
  it('shows a failing screen inside the app frame, sidebar and law switch kept', async () => {
    renderApp('/app/broken?law=original')

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
    expect(screen.getByRole('navigation', { name: 'App' })).toBeInTheDocument()
    const group = screen.getByRole('group', { name: 'Law version' })
    expect(group.querySelectorAll('button')[1]).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Guidance, not legal advice. Klar is an AI system.')).toBeVisible()
    expect(screen.queryByText('screen failed')).toBeNull()
  })

  it('keeps the same frame through an error and the recovery from it', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const router = renderApp('/app/working')
    await screen.findByRole('heading', { name: 'Working screen' })
    const before = frame()
    act(() => {
      vi.advanceTimersByTime(LOAD_MOTION_MS)
    })
    expect(before).not.toHaveClass('app-intro')

    // This router's paths aren't the registered app's, so go through its history.
    act(() => {
      router.history.push('/app/broken')
    })
    await screen.findByRole('alert')
    expect(frame()).toBe(before)
    expect(frame()).not.toHaveClass('app-intro')

    act(() => {
      router.history.push('/app/working')
    })
    await screen.findByRole('heading', { name: 'Working screen' })
    expect(screen.queryByRole('alert')).toBeNull()
    expect(frame()).toBe(before)
  })
})
