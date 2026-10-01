import { createFileRoute, Outlet, retainSearchParams } from '@tanstack/react-router'
import type { JSX, ReactNode } from 'react'

import { AppFrame } from '@/components/AppFrame'
import { ErrorView } from '@/components/ErrorView'
import type { LawVersion } from '@/components/LawSwitch'

/** The app's search params: `law=original` while the original 2024 text is shown. */
type AppSearch = { law?: Extract<LawVersion, 'original'> }

// Amended is the default and stays out of the address; anything else is dropped. `law` is always
// set, even to undefined: the router merges the raw address under the validated search, so an
// omitted key would let `law=bogus` through.
function validateAppSearch(search: Record<string, unknown>): AppSearch {
  return { law: search.law === 'original' ? 'original' : undefined }
}

/**
 * The app screens' frame. The law version is shareable view state, so it lives in the address
 * (frontend rule) and every link inside the app keeps it.
 */
export const Route = createFileRoute('/app')({
  validateSearch: validateAppSearch,
  search: { middlewares: [retainSearchParams(['law'])] },
  component: AppLayout,
  // A screen that fails keeps the sidebar and the law switch around the error.
  errorComponent: AppError,
})

function AppLayout(): JSX.Element {
  return (
    <BoundAppFrame>
      <Outlet />
    </BoundAppFrame>
  )
}

function AppError(): JSX.Element {
  return (
    <BoundAppFrame>
      <ErrorView />
    </BoundAppFrame>
  )
}

/** AppFrame with its law version switch bound to the `law` search param. */
function BoundAppFrame({ children }: { children: ReactNode }): JSX.Element {
  const { law } = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <AppFrame
      law={{
        value: law === 'original' ? 'original' : 'amended',
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
      {children}
    </AppFrame>
  )
}
