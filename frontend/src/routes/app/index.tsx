import { createFileRoute, redirect } from '@tanstack/react-router'

// The app's start opens the inventory; P18 sends a first visit to the Welcome screen instead.
export const Route = createFileRoute('/app/')({
  beforeLoad: ({ search }) => {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- the router's redirect is thrown
    throw redirect({ to: '/app/inventory', search })
  },
})
