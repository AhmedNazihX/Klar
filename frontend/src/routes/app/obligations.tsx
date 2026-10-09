import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'

import { ObligationsScreen, type ObligationsGroup } from '@/features/obligations/ObligationsScreen'

/** `group=tool` groups the duties by tool; By date is the default and stays out of the address.
 *  Like `law`, the key is always set so a bogus value can't slip through. */
type ObligationsSearch = { group?: Extract<ObligationsGroup, 'tool'> }

function validateObligationsSearch(search: Record<string, unknown>): ObligationsSearch {
  return { group: search.group === 'tool' ? 'tool' : undefined }
}

// Every duty across the inventory (P24; artboard `Obligations`).
export const Route = createFileRoute('/app/obligations')({
  validateSearch: validateObligationsSearch,
  component: ObligationsRoute,
  staticData: { titleKey: 'screen.obligations' },
})

function ObligationsRoute(): JSX.Element | null {
  const { group } = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <ObligationsScreen
      today={new Date()}
      group={group ?? 'date'}
      onGroupChange={(next) => {
        void navigate({
          search: (previous) => ({ ...previous, group: next === 'tool' ? 'tool' : undefined }),
          replace: true,
        })
      }}
    />
  )
}
