import {
  CatchBoundary,
  createFileRoute,
  Outlet,
  retainSearchParams,
  useNavigate,
  useRouterState,
  type ErrorComponentProps,
} from '@tanstack/react-router'
import { useEffect, useState, type JSX } from 'react'

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
})

// The screen boundary resets itself from ScreenError, not from a changing key.
const SCREEN_BOUNDARY_KEY = 'app-screen'

/**
 * A screen that fails shows the error in the screen area only. Going anywhere else clears it:
 * the boundary is reset once another screen has loaded.
 */
function ScreenError({ reset }: ErrorComponentProps): JSX.Element {
  // The screen on show: it changes only once the next screen is loaded and about to render,
  // so resetting then never re-renders the screen that failed.
  const screenId = useRouterState({ select: (state) => state.matches.at(-1)?.id })
  const [failedOn] = useState(screenId)
  useEffect(() => {
    if (screenId !== failedOn) reset()
  }, [screenId, failedOn, reset])
  return <ErrorView />
}

/**
 * One AppFrame for every screen, with its law version switch bound to the `law` search param.
 * The error boundary sits inside the frame, around the screen: a failing screen, and the way out
 * of it (ScreenError resets the boundary on the next navigation), never remount the frame, so
 * its state, its focus and its settled load motion survive. An error in the frame itself goes up
 * to the root, which shows it on the site frame.
 */
function AppLayout(): JSX.Element {
  const { law } = Route.useSearch()
  // Not bound to this layout route: the switch changes `law` on the screen on show and keeps its
  // path and its other search params (a tool's result, its view), as the language switch does.
  const navigate = useNavigate()
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
      <CatchBoundary getResetKey={() => SCREEN_BOUNDARY_KEY} errorComponent={ScreenError}>
        <Outlet />
      </CatchBoundary>
    </AppFrame>
  )
}
