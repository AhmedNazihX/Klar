import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'

import { validateDocumentSearch } from '@/features/documents/document-search'
import { DocumentsScreen } from '@/features/documents/DocumentsScreen'

// Draft documents (P9; artboard `Documents`): the first document of the first tool, or of `tool`.
export const Route = createFileRoute('/app/documents/')({
  validateSearch: validateDocumentSearch,
  component: DocumentsRoute,
  staticData: { titleKey: 'screen.documents' },
})

function DocumentsRoute(): JSX.Element {
  const { tool } = Route.useSearch()
  return <DocumentsScreen toolId={tool} />
}
