import type { QueryClient } from '@tanstack/react-query'
import { createRouter, type RouterHistory } from '@tanstack/react-router'

import type en from './i18n/locales/en.json'
import { routeTree } from './routeTree.gen'

/** A screen's title key: the top bar shows it (AppFrame). */
export type ScreenTitleKey = `screen.${Exclude<keyof typeof en.screen, 'placeholder'>}`

/** The app router. Tests pass a memory history (src/test/test-utils.tsx). */
export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: 'intent',
    scrollRestoration: true,
    ...(history ? { history } : {}),
  })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
  interface StaticDataRouteOption {
    titleKey?: ScreenTitleKey
  }
}
