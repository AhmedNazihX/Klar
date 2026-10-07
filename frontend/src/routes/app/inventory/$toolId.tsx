import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'

import { classificationRunOptions } from '@/features/classify/classification-store'
import type { ResultView } from '@/features/classify/ResultHeader'
import { ResultNotFound, ResultScreen } from '@/features/classify/ResultScreen'

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
  const run = useQuery(classificationRunOptions(toolId))
  if (run.isPending) return null
  if (!run.data) return <ResultNotFound />
  return (
    <ResultScreen
      run={run.data}
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
