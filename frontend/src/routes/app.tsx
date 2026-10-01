import { createFileRoute, Outlet, retainSearchParams } from '@tanstack/react-router'
import type { JSX } from 'react'

import { AppFrame } from '@/components/AppFrame'
import type { LawVersion } from '@/components/LawSwitch'

/** The app's search params: `law=original` while the original 2024 text is shown. */
export type AppSearch = { law?: Extract<LawVersion, 'original'> }

// Amended is the default and stays out of the address; anything else is dropped.
function validateAppSearch(search: Record<string, unknown>): AppSearch {
  return search.law === 'original' ? { law: 'original' } : {}
}

/**
 * The app screens' frame. The law version is shareable view state, so it lives in the address
 * (frontend rule) and every link inside the app keeps it.
 */
export const Route = createFileRoute('/app')({
  validateSearch: validateAppSearch,
  search: { middlewares: [retainSearchParams(['law'])] },
  component: AppLayout,
})

function AppLayout(): JSX.Element {
  const { law } = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <AppFrame
      law={{
        value: law ?? 'amended',
        onChange: (next) => {
          void navigate({
            to: '.',
            search: (previous) => ({
              ...previous,
              law: next === 'original' ? 'original' : undefined,
            }),
            replace: true,
          })
        },
      }}
    >
      <Outlet />
    </AppFrame>
  )
}
