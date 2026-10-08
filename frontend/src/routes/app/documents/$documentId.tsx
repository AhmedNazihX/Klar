import { createFileRoute } from '@tanstack/react-router'
import type { JSX } from 'react'

import { validateDocumentSearch } from '@/features/documents/document-search'
import { DocumentsScreen } from '@/features/documents/DocumentsScreen'

// One draft document (P9; artboards `Documents`, `DocSkeleton`), keyed by its template id and,
// with `?tool=`, the tool it belongs to; without it, the first tool that has the document.
export const Route = createFileRoute('/app/documents/$documentId')({
  validateSearch: validateDocumentSearch,
  component: DocumentRoute,
  staticData: { titleKey: 'screen.document' },
})

function DocumentRoute(): JSX.Element {
  const { documentId } = Route.useParams()
  const { tool } = Route.useSearch()
  return <DocumentsScreen documentId={documentId} toolId={tool} />
}
