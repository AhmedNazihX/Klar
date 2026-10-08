import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'

import { toolResultOptions } from '@/features/classify/classification-store'
import type { ResultView } from '@/features/classify/ResultHeader'
import { ResultNotFound, ResultScreen } from '@/features/classify/ResultScreen'
import { ToolWithoutResult } from '@/features/classify/ToolWithoutResult'
import { supabase } from '@/lib/supabase'

/** `view=reviewer` opens the reviewer view; the summary is the default and stays out of the
 *  address. Like `law`, the key is always set so a bogus value can't slip through. */
type ResultSearch = { view?: Extract<ResultView, 'reviewer'> }

function validateResultSearch(search: Record<string, unknown>): ResultSearch {
  return { view: search.view === 'reviewer' ? 'reviewer' : undefined }
}

// A tool's result (P5; artboards `Result`, `Reviewer`, `ResultNeedsInfo`). The other result
// layouts (prohibited, ambiguous, provider, phone, German review) are P21–P23, P26 and P11.
export const Route = createFileRoute('/app/inventory/$toolId')({
  validateSearch: validateResultSearch,
  component: ResultRoute,
  staticData: { titleKey: 'screen.result' },
})

function ResultRoute(): JSX.Element | null {
  const { toolId } = Route.useParams()
  const { view } = Route.useSearch()
  const navigate = Route.useNavigate()
  const queryClient = useQueryClient()
  const page = useQuery(toolResultOptions(queryClient, supabase, toolId))
  // A read that failed shows the screen's ErrorView (routes/app.tsx), not "not found".
  if (page.isError) throw page.error
  if (page.isPending) return null
  // Without a run to show, the tool itself says why: never checked, unreadable, or not there.
  if (page.data.kind === 'missing') return <ResultNotFound />
  if (page.data.kind !== 'run') {
    return (
      <ToolWithoutResult tool={page.data.tool} isUnreadable={page.data.kind === 'unreadable'} />
    )
  }
  return (
    // Keyed by tool: another tool's page starts with its own original-text run, not this one's.
    <ResultScreen
      key={toolId}
      run={page.data.run}
      view={view ?? 'summary'}
      onViewChange={(next) => {
        void navigate({
          search: (previous) => ({
            ...previous,
            view: next === 'reviewer' ? 'reviewer' : undefined,
          }),
          replace: true,
        })
      }}
    />
  )
}
